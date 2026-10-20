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
 valid_to REAL, supersedes TEXT UNIQUE REFERENCES facts(id),
 created_at REAL NOT NULL, strength REAL NOT NULL, last_accessed REAL NOT NULL,
 provenance TEXT NOT NULL, CHECK(valid_to IS NULL OR valid_to >= valid_from));
CREATE UNIQUE INDEX IF NOT EXISTS one_head ON facts(scope,subject,predicate) WHERE valid_to IS NULL;
CREATE TABLE IF NOT EXISTS vectors(fact_id TEXT PRIMARY KEY REFERENCES facts(id),vector BLOB NOT NULL);
CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(fact_id UNINDEXED,text);
CREATE TABLE IF NOT EXISTS edges(scope TEXT,source TEXT,target TEXT,predicate TEXT,weight REAL,
 PRIMARY KEY(scope,source,target,predicate));
CREATE TABLE IF NOT EXISTS receipts(seq INTEGER PRIMARY KEY,payload TEXT NOT NULL,
 previous_hash TEXT NOT NULL,receipt_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
INSERT OR IGNORE INTO metadata VALUES('schema_version','1');
"""

class MemoryEngine(Operations, Audit, Ranking):
    def __init__(self, path=':memory:', *, clock=None, embedder=None):
        self.path = str(path)
        self.clock = clock or SystemClock()
        self.embedder = embedder or AsyncHashingEmbedder()
        self.db = None
        self._lock = asyncio.Lock()

    async def setup(self):
        if self.db is not None:
            raise RuntimeError('Engine already open')
        self.db = await aiosqlite.connect(self.path, isolation_level=None)
        self.db.row_factory = aiosqlite.Row
        try:
            await self.db.execute('PRAGMA foreign_keys=ON')
            await self.db.execute('PRAGMA busy_timeout=5000')
            await self.db.execute('PRAGMA journal_mode=WAL')
            await self.db.execute('PRAGMA synchronous=FULL')
            # Existing foreign schemas must never be silently adopted.
            tables = await self._rows("SELECT name FROM sqlite_master WHERE type='table'")
            if tables:
                if not any(r['name']=='metadata' for r in tables):
                    raise ValueError('Unrecognized database: export/import migration required')
                version = await self._rows("SELECT value FROM metadata WHERE key='schema_version'")
                if not version or version[0]['value'] != '1':
                    raise ValueError('Unsupported schema version')
            await self.db.executescript(SCHEMA)
            await self.verify()
            return self
        except BaseException:
            await self.db.close()
            self.db = None
            raise

    async def close(self):
        async with self._lock:
            if self.db:
                await self.db.close()
                self.db = None

    async def __aenter__(self):
        return await self.setup()

    async def __aexit__(self, *args):
        await self.close()

    def _require(self):
        if self.db is None:
            raise RuntimeError('Database not connected')

    async def _rows(self, sql, args=()):
        self._require()
        async with self.db.execute(sql,args) as cur:
            return [dict(row) for row in await cur.fetchall()]

    @asynccontextmanager
    async def _transaction(self, write=False):
        async with self._lock:
            self._require()
            await self.db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            try:
                yield
                await self.db.commit()
            except BaseException:
                await self.db.rollback()
                raise

    def _now(self):
        now=float(self.clock.now())
        if not math.isfinite(now):
            raise ValueError('Clock must be finite')
        return now
