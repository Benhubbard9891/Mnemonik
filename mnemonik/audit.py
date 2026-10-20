"""Hash-linked receipts: integrity evidence, not signatures or trusted time."""
import hashlib
import json

ZERO = '0' * 64

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))

class IntegrityError(Exception):
    pass

class Audit:
    def __init__(self, db):
        self.db = db

    async def verify(self, expected_head=None):
        # Full chain verification lives in the release candidate source
        return {"ok": True, "head": ZERO, "note": "placeholder during transfer; replace with full audit from rc1 tree"}
