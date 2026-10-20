"""Hash-linked receipts: integrity evidence, not signatures or trusted time."""
import hashlib
import json

ZERO='0'*64

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

class IntegrityError(ValueError):
    pass

class Audit:
    async def _state(self):
        return {
            'facts': await self._rows('SELECT * FROM facts ORDER BY id'),
            'vectors': await self._rows('SELECT fact_id,hex(vector) AS vector FROM vectors ORDER BY fact_id'),
            'fts': await self._rows('SELECT fact_id,text FROM facts_fts ORDER BY fact_id'),
            'edges': await self._rows('SELECT * FROM edges ORDER BY scope,source,target,predicate'),
        }

    async def _append_receipt(self, operation, fact_id, actor, evidence, timestamp):
        rows=await self._rows('SELECT * FROM receipts ORDER BY seq DESC LIMIT 1')
        previous=rows[0]['receipt_hash'] if rows else ZERO
        seq=rows[0]['seq']+1 if rows else 1
        payload={'seq':seq,'operation':operation,'fact_id':fact_id,'actor':actor,
                 'evidence':evidence,'timestamp':timestamp,'state_hash':digest(await self._state())}
        receipt_hash=digest({'previous_hash':previous,'payload':payload})
        await self.db.execute('INSERT INTO receipts VALUES(?,?,?,?)',
                              (seq,canonical(payload),previous,receipt_hash))
        return receipt_hash

    async def _verify(self, expected_head=None):
        rows=await self._rows('SELECT * FROM receipts ORDER BY seq')
        previous=ZERO
        last=None
        for seq,row in enumerate(rows,1):
            try:
                payload=json.loads(row['payload'])
                valid=(row['seq']==seq and payload['seq']==seq and row['previous_hash']==previous
                       and row['receipt_hash']==digest({'previous_hash':previous,'payload':payload}))
            except (ValueError,KeyError,TypeError):
                valid=False
            if not valid:
                raise IntegrityError('Receipt chain mismatch')
            previous=row['receipt_hash']; last=payload
        state=await self._state()
        if last is None:
            if any(state.values()):
                raise IntegrityError('State exists without receipts')
        elif last['state_hash'] != digest(state):
            raise IntegrityError('State/index hash mismatch')
        if expected_head is not None and previous != expected_head:
            raise IntegrityError('Externally retained receipt head mismatch')
        return {'receipts':len(rows),'head':previous,'state_hash':digest(state)}

    async def verify(self, expected_head=None):
        async with self._transaction():
            result=await self._verify(expected_head)
            check=await self._rows('PRAGMA integrity_check')
            if list(check[0].values()) != ['ok'] or await self._rows('PRAGMA foreign_key_check'):
                raise IntegrityError('SQLite integrity check failed')
            return result

    async def snapshot(self):
        async with self._transaction():
            return {'state':await self._state(),'receipts':await self._rows('SELECT * FROM receipts ORDER BY seq')}

    async def receipts(self):
        async with self._transaction():
            return await self._rows('SELECT * FROM receipts ORDER BY seq')
