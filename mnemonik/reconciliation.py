"""Ranking primitives extracted from the v3.1 verification notebook."""
import math
import re
import json
import aiosqlite
from .models import Fact

class Ranking:
    @staticmethod
    def _fact_text(fact: Fact) -> str:
        return f"{fact.subject} {fact.predicate} {fact.object}"

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        # Extract alphanumeric tokens to prevent FTS5 syntax errors
        return re.findall(r"\w+", text.lower())

    @staticmethod
    def _row_to_fact(row: aiosqlite.Row) -> Fact:
        return Fact(
            id=row["id"], subject=row["subject"], predicate=row["predicate"],
            object=row["object"], scope=row["scope"], valid_from=row["valid_from"],
            valid_to=row["valid_to"], supersedes=row["supersedes"], created_at=row["created_at"],
            strength=row["strength"], last_accessed=row["last_accessed"], provenance=row["provenance"],
        )

    async def _dense_rank(self, query: str, candidates: list[Fact]) -> list[tuple[Fact, float]]:
        if not self.db or not candidates: return []
        query_vector = await self.embedder.embed(query)
        query_dim = len(query_vector)
        query_norm = math.sqrt(sum(v * v for v in query_vector))

        # One batched fetch for all candidates — not one round-trip per fact.
        placeholders = ",".join("?" for _ in candidates)
        async with self.db.execute(
            f"SELECT fact_id, vector FROM vectors WHERE fact_id IN ({placeholders})",
            [fact.id for fact in candidates],
        ) as cursor:
            rows = await cursor.fetchall()
        vectors = {row["fact_id"]: row["vector"] for row in rows}

        scored: list[tuple[Fact, float]] = []
        for fact in candidates:
            blob = vectors.get(fact.id)
            if blob is None: continue

            stored_vector = json.loads(bytes(blob).decode("utf-8"))
            if len(stored_vector) != query_dim:
                raise ValueError(
                    f"Embedding dimension mismatch for fact {fact.id}: "
                    f"stored={len(stored_vector)}, query={query_dim}"
                )
            right_norm = math.sqrt(sum(v * v for v in stored_vector))
            if query_norm <= 1e-12 or right_norm <= 1e-12:
                score = 0.0
            else:
                dot = sum(l * r for l, r in zip(query_vector, stored_vector))
                score = dot / (query_norm * right_norm)

            scored.append((fact, score))
        return sorted(scored, key=lambda item: (item[1], item[0].strength), reverse=True)

    async def _sparse_rank(self, query: str, candidates: list[Fact]) -> list[tuple[Fact, float]]:
        """Powered by SQLite FTS5 BM25 scoring."""
        if not self.db: return []

        tokens = self._tokenize(query)
        if not tokens:
            return []

        # Create a simple OR query string for FTS5 (e.g. "token1 OR token2")
        fts_query = " OR ".join('"' + token + '"' for token in tokens)

        # SQLite FTS5 bm25() returns negative values where more negative is better.
        # We negate it so higher = better, aligning with dense and graph scores.
        async with self.db.execute(
            "SELECT fact_id, -bm25(facts_fts) as score FROM facts_fts WHERE facts_fts MATCH ?",
            (fts_query,)
        ) as cursor:
            rows = await cursor.fetchall()

        scores = {row["fact_id"]: float(row["score"]) for row in rows}
        candidate_ids = {fact.id for fact in candidates}

        scored: list[tuple[Fact, float]] = []
        for fact in candidates:
            if fact.id in scores:
                scored.append((fact, scores[fact.id]))

        return sorted(scored, key=lambda item: (item[1], item[0].strength), reverse=True)
