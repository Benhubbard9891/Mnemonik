class MnemonikMemoryStore:
    def __init__(self, db, clock):
        self.db = db
        self.clock = clock

    async def prune_memory(
        self,
        threshold: float = 0.1,
        half_life_seconds: float = 604800.0,
    ) -> int:
        if self.db is None:
            raise RuntimeError("Database not connected.")
        if not (0.0 <= threshold <= 1.0):
            raise ValueError(f"threshold must be in [0.0, 1.0], got {threshold}")
        if half_life_seconds <= 0:
            raise ValueError(f"half_life_seconds must be > 0, got {half_life_seconds}")

        now = self.clock.now()
        pruned_count = 0

        async with self.db.execute(
            "SELECT id, strength, last_accessed FROM facts WHERE valid_to IS NULL"
        ) as cursor:
            active_facts = await cursor.fetchall()

        for row in active_facts:
            fact_id = row["id"]
            strength = row["strength"]
            last_accessed = row["last_accessed"]

            elapsed = max(0.0, now - last_accessed)
            retrievability = strength * (0.5 ** (elapsed / half_life_seconds))

            if retrievability < threshold:
                await self.db.execute(
                    "UPDATE facts SET valid_to = ? WHERE id = ?",
                    (now, fact_id),
                )
                await self.db.execute(
                    "DELETE FROM vectors WHERE fact_id = ?",
                    (fact_id,),
                )
                await self.db.execute(
                    "DELETE FROM facts_fts WHERE fact_id = ?",
                    (fact_id,),
                )
                pruned_count += 1

        if pruned_count > 0:
            await self.db.commit()

        return pruned_count

    async def reinforce_fact(
        self,
        fact_id: str,
        reinforcement_value: float = 0.2,
    ) -> None:
        if self.db is None:
            raise RuntimeError("Database not connected.")

        now = self.clock.now()

        await self.db.execute(
            """
            UPDATE facts
            SET last_accessed = ?,
                strength = MIN(1.0, strength + ?)
            WHERE id = ?
            """,
            (now, reinforcement_value, fact_id),
        )
        await self.db.commit()
