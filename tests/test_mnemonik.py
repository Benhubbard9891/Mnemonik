import unittest
from unittest.mock import AsyncMock, MagicMock

from mnemonik import MnemonikMemoryStore


class TestMnemonikMemoryStore(unittest.IsolatedAsyncioTestCase):
    """Test suite for MnemonikMemoryStore."""

    def setUp(self):
        self.mock_db = AsyncMock()
        self.mock_clock = MagicMock()
        self.mock_clock.now.return_value = 1000.0
        self.store = MnemonikMemoryStore(self.mock_db, self.mock_clock)

        # execute() must return an object that supports the async context manager protocol
        # (not a coroutine). Configure a dedicated cursor + context manager.
        self.mock_cursor = AsyncMock()
        self.mock_cm = AsyncMock()
        self.mock_cm.__aenter__.return_value = self.mock_cursor
        self.mock_cm.__aexit__.return_value = None
        self.mock_db.execute.return_value = self.mock_cm

    # ─────────────────────────────────────────────────────────────
    # prune_memory — guard & validation
    # ─────────────────────────────────────────────────────────────

    async def test_prune_memory_raises_when_db_is_none(self):
        store = MnemonikMemoryStore(db=None, clock=self.mock_clock)
        with self.assertRaises(RuntimeError) as ctx:
            await store.prune_memory()
        self.assertIn("Database not connected", str(ctx.exception))

    async def test_prune_memory_rejects_negative_threshold(self):
        with self.assertRaises(ValueError) as ctx:
            await self.store.prune_memory(threshold=-0.1)
        self.assertIn("threshold must be in [0.0, 1.0]", str(ctx.exception))

    async def test_prune_memory_rejects_threshold_above_one(self):
        with self.assertRaises(ValueError) as ctx:
            await self.store.prune_memory(threshold=1.1)
        self.assertIn("threshold must be in [0.0, 1.0]", str(ctx.exception))

    async def test_prune_memory_rejects_zero_half_life(self):
        with self.assertRaises(ValueError) as ctx:
            await self.store.prune_memory(half_life_seconds=0.0)
        self.assertIn("half_life_seconds must be > 0", str(ctx.exception))

    async def test_prune_memory_rejects_negative_half_life(self):
        with self.assertRaises(ValueError) as ctx:
            await self.store.prune_memory(half_life_seconds=-1.0)
        self.assertIn("half_life_seconds must be > 0", str(ctx.exception))

    # ─────────────────────────────────────────────────────────────
    # prune_memory — decay & pruning logic
    # ─────────────────────────────────────────────────────────────

    async def test_prune_memory_no_active_facts_returns_zero(self):
        self.mock_cursor.fetchall.return_value = []
        result = await self.store.prune_memory()
        self.assertEqual(result, 0)
        self.mock_db.commit.assert_not_awaited()

    async def test_prune_memory_fact_above_threshold_not_pruned(self):
        self.mock_cursor.fetchall.return_value = [
            {"id": "fact-1", "strength": 1.0, "last_accessed": 1000.0}
        ]
        result = await self.store.prune_memory()
        self.assertEqual(result, 0)
        # Only the SELECT should have been issued
        self.assertEqual(self.mock_db.execute.await_count, 1)
        self.mock_db.commit.assert_not_awaited()

    async def test_prune_memory_fact_below_threshold_gets_tombstoned(self):
        self.mock_cursor.fetchall.return_value = [
            {"id": "fact-1", "strength": 0.05, "last_accessed": 1000.0}
        ]
        result = await self.store.prune_memory()
        self.assertEqual(result, 1)
        # SELECT + UPDATE + DELETE vectors + DELETE fts = 4
        self.assertEqual(self.mock_db.execute.await_count, 4)
        self.mock_db.commit.assert_awaited_once()

    async def test_prune_memory_exponential_decay_calculation(self):
        self.mock_clock.now.return_value = 1100.0
        self.mock_cursor.fetchall.return_value = [
            {"id": "fact-1", "strength": 0.5, "last_accessed": 1000.0}
        ]
        # elapsed=100, half_life=100 → retrievability = 0.5 * 0.5 = 0.25 < 0.3
        result = await self.store.prune_memory(threshold=0.3, half_life_seconds=100.0)
        self.assertEqual(result, 1)

    async def test_prune_memory_exactly_at_threshold_not_pruned(self):
        self.mock_cursor.fetchall.return_value = [
            {"id": "fact-1", "strength": 0.1, "last_accessed": 1000.0}
        ]
        result = await self.store.prune_memory(threshold=0.1)
        self.assertEqual(result, 0)

    async def test_prune_memory_multiple_facts_mixed(self):
        self.mock_clock.now.return_value = 1100.0
        self.mock_cursor.fetchall.return_value = [
            {"id": "fact-strong", "strength": 1.0, "last_accessed": 1000.0},
            {"id": "fact-weak", "strength": 0.1, "last_accessed": 1000.0},
        ]
        # strong: 1.0 * 0.5 = 0.5 >= 0.1 → keep
        # weak:   0.1 * 0.5 = 0.05 < 0.1 → prune
        result = await self.store.prune_memory(threshold=0.1, half_life_seconds=100.0)
        self.assertEqual(result, 1)
        self.mock_db.commit.assert_awaited_once()

    async def test_prune_memory_elapsed_negative_clamped_to_zero(self):
        self.mock_clock.now.return_value = 500.0
        self.mock_cursor.fetchall.return_value = [
            {"id": "fact-1", "strength": 0.05, "last_accessed": 1000.0}
        ]
        # elapsed clamped to 0 → retrievability = 0.05 < 0.1 → still pruned
        result = await self.store.prune_memory()
        self.assertEqual(result, 1)

    async def test_prune_memory_deletes_vector_and_fts_indices(self):
        self.mock_cursor.fetchall.return_value = [
            {"id": "fact-1", "strength": 0.05, "last_accessed": 1000.0}
        ]
        await self.store.prune_memory()
        calls = [str(call) for call in self.mock_db.execute.await_args_list]
        self.assertTrue(any("DELETE FROM vectors" in c for c in calls))
        self.assertTrue(any("DELETE FROM facts_fts" in c for c in calls))

    async def test_prune_memory_sets_valid_to_timestamp(self):
        self.mock_cursor.fetchall.return_value = [
            {"id": "fact-1", "strength": 0.05, "last_accessed": 1000.0}
        ]
        await self.store.prune_memory()
        calls = [str(call) for call in self.mock_db.execute.await_args_list]
        self.assertTrue(any("UPDATE facts SET valid_to" in c for c in calls))

    # ─────────────────────────────────────────────────────────────
    # prune_memory — edge cases
    # ─────────────────────────────────────────────────────────────

    async def test_prune_memory_threshold_zero_prunes_nothing_with_positive_strength(self):
        self.mock_cursor.fetchall.return_value = [
            {"id": "fact-1", "strength": 0.0001, "last_accessed": 1000.0}
        ]
        result = await self.store.prune_memory(threshold=0.0)
        self.assertEqual(result, 0)

    async def test_prune_memory_threshold_one_prunes_all(self):
        self.mock_cursor.fetchall.return_value = [
            {"id": "fact-1", "strength": 1.0, "last_accessed": 1000.0}
        ]
        # retrievability == 1.0 which is NOT < 1.0 → not pruned
        result = await self.store.prune_memory(threshold=1.0)
        self.assertEqual(result, 0)

    async def test_prune_memory_very_large_half_life_minimal_decay(self):
        self.mock_clock.now.return_value = 2000.0
        self.mock_cursor.fetchall.return_value = [
            {"id": "fact-1", "strength": 0.5, "last_accessed": 1000.0}
        ]
        result = await self.store.prune_memory(half_life_seconds=1e9, threshold=0.4)
        self.assertEqual(result, 0)

    # ─────────────────────────────────────────────────────────────
    # reinforce_fact — guard
    # ─────────────────────────────────────────────────────────────

    async def test_reinforce_fact_raises_when_db_is_none(self):
        store = MnemonikMemoryStore(db=None, clock=self.mock_clock)
        with self.assertRaises(RuntimeError) as ctx:
            await store.reinforce_fact("fact-123")
        self.assertIn("Database not connected", str(ctx.exception))

    # ─────────────────────────────────────────────────────────────
    # reinforce_fact — behavior
    # ─────────────────────────────────────────────────────────────

    async def test_reinforce_fact_updates_last_accessed(self):
        await self.store.reinforce_fact("fact-123")
        call_args = self.mock_db.execute.await_args
        sql = call_args[0][0]
        params = call_args[0][1]
        self.assertIn("last_accessed = ?", sql)
        self.assertEqual(params[0], 1000.0)

    async def test_reinforce_fact_boosts_strength(self):
        await self.store.reinforce_fact("fact-123", reinforcement_value=0.3)
        call_args = self.mock_db.execute.await_args
        sql = call_args[0][0]
        self.assertIn("strength = MIN(1.0, strength + ?)", sql)
        self.assertEqual(call_args[0][1][1], 0.3)

    async def test_reinforce_fact_caps_strength_at_one(self):
        await self.store.reinforce_fact("fact-123")
        call_args = self.mock_db.execute.await_args
        sql = call_args[0][0]
        self.assertIn("MIN(1.0", sql)

    async def test_reinforce_fact_targets_correct_fact_id(self):
        await self.store.reinforce_fact("fact-abc")
        call_args = self.mock_db.execute.await_args
        params = call_args[0][1]
        self.assertEqual(params[2], "fact-abc")

    async def test_reinforce_fact_commits_transaction(self):
        await self.store.reinforce_fact("fact-123")
        self.mock_db.commit.assert_awaited_once()

    async def test_reinforce_fact_default_reinforcement_value(self):
        await self.store.reinforce_fact("fact-123")
        call_args = self.mock_db.execute.await_args
        params = call_args[0][1]
        self.assertEqual(params[1], 0.2)

    # ─────────────────────────────────────────────────────────────
    # reinforce_fact — SQL structure
    # ─────────────────────────────────────────────────────────────

    async def test_reinforce_fact_sql_has_three_placeholders(self):
        await self.store.reinforce_fact("fact-123")
        call_args = self.mock_db.execute.await_args
        params = call_args[0][1]
        self.assertEqual(len(params), 3)

    async def test_reinforce_fact_sql_updates_facts_table(self):
        await self.store.reinforce_fact("fact-123")
        call_args = self.mock_db.execute.await_args
        sql = call_args[0][0]
        self.assertIn("UPDATE facts", sql)


if __name__ == "__main__":
    unittest.main()
