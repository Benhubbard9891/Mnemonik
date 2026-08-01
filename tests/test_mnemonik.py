import unittest

from mnemonik import MnemonikMemoryStore


class FakeClock:
    def __init__(self, now):
        self._now = now

    def now(self):
        return self._now


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def fetchall(self):
        return self._rows


class FakeDB:
    def __init__(self, facts):
        self.facts = {fact["id"]: dict(fact) for fact in facts}
        self.vectors = {fact["id"] for fact in facts}
        self.fts = {fact["id"] for fact in facts}
        self.commit_calls = 0

    def execute(self, query, params=()):
        if query.startswith("SELECT id, strength, last_accessed FROM facts"):
            active_facts = [
                {
                    "id": fact["id"],
                    "strength": fact["strength"],
                    "last_accessed": fact["last_accessed"],
                }
                for fact in self.facts.values()
                if fact.get("valid_to") is None
            ]
            return FakeCursor(active_facts)
        return _ExecuteOperation(self, query, params)

    async def commit(self):
        self.commit_calls += 1


class _ExecuteOperation:
    def __init__(self, db, query, params):
        self.db = db
        self.query = query
        self.params = params

    def __await__(self):
        return self._run().__await__()

    async def _run(self):
        if self.query.startswith("UPDATE facts SET valid_to"):
            valid_to, fact_id = self.params
            self.db.facts[fact_id]["valid_to"] = valid_to
        elif self.query.startswith("DELETE FROM vectors"):
            fact_id = self.params[0]
            self.db.vectors.discard(fact_id)
        elif self.query.startswith("DELETE FROM facts_fts"):
            fact_id = self.params[0]
            self.db.fts.discard(fact_id)
        elif "UPDATE facts" in self.query and "strength = MIN(1.0, strength + ?)" in self.query:
            now, reinforcement_value, fact_id = self.params
            fact = self.db.facts[fact_id]
            fact["last_accessed"] = now
            fact["strength"] = min(1.0, fact["strength"] + reinforcement_value)
        return None


class MnemonikMemoryStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_prune_memory_counts_every_pruned_fact(self):
        db = FakeDB(
            [
                {"id": "prune-1", "strength": 0.05, "last_accessed": 0.0, "valid_to": None},
                {"id": "prune-2", "strength": 0.09, "last_accessed": 0.0, "valid_to": None},
                {"id": "keep", "strength": 0.9, "last_accessed": 95.0, "valid_to": None},
            ]
        )
        store = MnemonikMemoryStore(db=db, clock=FakeClock(100.0))

        pruned = await store.prune_memory(threshold=0.1, half_life_seconds=1000.0)

        self.assertEqual(pruned, 2)
        self.assertEqual(db.facts["prune-1"]["valid_to"], 100.0)
        self.assertEqual(db.facts["prune-2"]["valid_to"], 100.0)
        self.assertIsNone(db.facts["keep"]["valid_to"])
        self.assertNotIn("prune-1", db.vectors)
        self.assertNotIn("prune-2", db.fts)
        self.assertEqual(db.commit_calls, 1)

    async def test_prune_memory_skips_commit_when_nothing_pruned(self):
        db = FakeDB(
            [
                {"id": "keep", "strength": 1.0, "last_accessed": 95.0, "valid_to": None},
            ]
        )
        store = MnemonikMemoryStore(db=db, clock=FakeClock(100.0))

        pruned = await store.prune_memory(threshold=0.1, half_life_seconds=1000.0)

        self.assertEqual(pruned, 0)
        self.assertEqual(db.commit_calls, 0)

    async def test_reinforce_fact_updates_timestamp_and_caps_strength(self):
        db = FakeDB(
            [
                {"id": "fact-1", "strength": 0.9, "last_accessed": 10.0, "valid_to": None},
            ]
        )
        store = MnemonikMemoryStore(db=db, clock=FakeClock(100.0))

        await store.reinforce_fact("fact-1", reinforcement_value=0.2)

        self.assertEqual(db.facts["fact-1"]["last_accessed"], 100.0)
        self.assertEqual(db.facts["fact-1"]["strength"], 1.0)
        self.assertEqual(db.commit_calls, 1)

    async def test_missing_database_raises_runtime_error(self):
        store = MnemonikMemoryStore(db=None, clock=FakeClock(100.0))

        with self.assertRaises(RuntimeError):
            await store.prune_memory()

        with self.assertRaises(RuntimeError):
            await store.reinforce_fact("fact-1")
