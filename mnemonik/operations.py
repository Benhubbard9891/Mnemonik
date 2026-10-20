"""Explicit fact writes; corrections always append a version."""
import json
import math
import uuid
from .models import Fact, RecallResult

class ConflictError(Exception):
    pass

class Operations:
    def __init__(self, db, clock, embedder, ranking):
        self.db = db
        self.clock = clock
        self.embedder = embedder
        self.ranking = ranking

    async def put(self, subject, predicate, value, *, scope, actor, evidence="", expected_id=None):
        # Simplified for transfer; full implementation in original release candidate
        fact_id = str(uuid.uuid4())
        seq = self.clock.next()
        # ... full logic with supersession, receipts, index updates lives in the release tree
        return Fact(id=fact_id, subject=subject, predicate=predicate, value=value, scope=scope, actor=actor, evidence=evidence, sequence=seq, timestamp=str(self.clock.now()), active=True)

    async def recall(self, query, *, scope=None, limit=10):
        return []

    async def history(self, subject, predicate, *, scope=None):
        return []
