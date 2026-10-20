"""Persistent, single-connection async memory engine."""
import asyncio
import math
from contextlib import asynccontextmanager
import aiosqlite
from .models import SystemClock
from .providers import AsyncHashingEmbedder
from .reconciliation import Ranking
from .operations import Operations
from .audit import Audit

SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
 id TEXT PRIMARY KEY, subject TEXT NOT NULL, predicate TEXT NOT NULL,
 object TEXT NOT NULL, scope TEXT NOT NULL, valid_from REAL NOT NULL,
 valid_to REAL, actor TEXT NOT NULL, evidence TEXT, supersedes TEXT,
 sequence INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_facts_subject ON facts(subject);
CREATE INDEX IF NOT EXISTS idx_facts_scope ON facts(scope);
CREATE INDEX IF NOT EXISTS idx_facts_active ON facts(active);
CREATE TABLE IF NOT EXISTS receipts (
 id TEXT PRIMARY KEY, sequence INTEGER NOT NULL, actor TEXT NOT NULL,
 ts REAL NOT NULL, evidence TEXT, operation TEXT NOT NULL,
 fact_id TEXT NOT NULL, state_hash TEXT NOT NULL, prev_hash TEXT NOT NULL,
 head TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

class MemoryEngine:
    def __init__(self, path: str, embedder=None, ranking=None):
        self.path = path
        self.embedder = embedder or AsyncHashingEmbedder()
        self.ranking = ranking or Ranking()
        self._db = None
        self._ops = None
        self._audit = None
        self._clock = SystemClock()

    async def __aenter__(self):
        self._db = await aiosqlite.connect(self.path)
        await self._db.executescript(SCHEMA)
        await self._db.commit()
        self._ops = Operations(self._db, self._clock, self.embedder, self.ranking)
        self._audit = Audit(self._db)
        return self

    async def __aexit__(self, *args):
        if self._db:
            await self._db.close()

    async def put(self, subject, predicate, value, *, scope, actor, evidence="", expected_id=None):
        return await self._ops.put(subject, predicate, value, scope=scope, actor=actor, evidence=evidence, expected_id=expected_id)

    async def recall(self, query, *, scope=None, limit=10):
        return await self._ops.recall(query, scope=scope, limit=limit)

    async def history(self, subject, predicate, *, scope=None):
        return await self._ops.history(subject, predicate, scope=scope)

    async def audit(self, expected_head=None):
        return await self._audit.verify(expected_head=expected_head)
