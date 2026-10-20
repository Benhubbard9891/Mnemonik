"""Explicit fact writes; corrections always append a version."""
import json
import math
import uuid
from .models import Fact, RecallResult

class ConflictError(ValueError):
    pass


def clean(value, label):
    if not isinstance(value,str) or not value.strip():
        raise ValueError(f'{label} must be nonempty text')
    return value.strip()

class Operations:
    async def put(self, subject, predicate, value, *, scope, actor, evidence='', expected_id=None):
        """One active value per (scope,subject,predicate); optional optimistic guard.

        expected_id='' requires no existing head. None permits serialized upsert.
        actor is caller-declared attribution, not an authenticated identity.
        """
        subject,predicate,value,scope,actor=[clean(v,k) for v,k in
            [(subject,'subject'),(predicate,'predicate'),(value,'value'),(scope,'scope'),(actor,'actor')]]
        if not isinstance(evidence,str):
            raise ValueError('evidence must be text')
        async with self._transaction(write=True):
            await self._verify()
            rows=await self._rows('SELECT * FROM facts WHERE scope=? AND subject=? AND predicate=? AND valid_to IS NULL',
                                 (scope,subject,predicate))
            old=rows[0] if rows else None
            if expected_id is not None and expected_id != (old['id'] if old else ''):
                raise ConflictError('Active version changed or target outside subject/scope')
            now=self._now()
            last=await self._rows('SELECT payload FROM receipts ORDER BY seq DESC LIMIT 1')
            if last and now < json.loads(last[0]['payload'])['timestamp']:
                raise ValueError('Clock moved backwards')
            operation='NOOP' if old and old['object']==value else ('SUPERSEDE' if old else 'ADD')
            if operation=='NOOP':
                fact=Fact(**old)
            else:
                if old:
                    await self.db.execute('UPDATE facts SET valid_to=? WHERE id=?',(now,old['id']))
                fact=Fact(id=uuid.uuid4().hex,subject=subject,predicate=predicate,object=value,scope=scope,
                          valid_from=now,valid_to=None,supersedes=old['id'] if old else None,
                          created_at=now,strength=1.0,last_accessed=now,
                          provenance=json.dumps({'actor':actor,'evidence':evidence},sort_keys=True))
                await self.db.execute('INSERT INTO facts VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',tuple(vars(fact).values()))
                await self._rebuild_indexes()
            await self._append_receipt(operation,fact.id,actor,evidence,now)
            return fact

    async def _rebuild_indexes(self):
        # All changes share the enclosing write transaction, including failure/cancellation.
        for table in ('vectors','facts_fts','edges'):
            await self.db.execute(f'DELETE FROM {table}')
        facts=[Fact(**r) for r in await self._rows('SELECT * FROM facts ORDER BY id')]
        texts=[self._fact_text(f) for f in facts]
        vectors=await self.embedder.embed_batch(texts)
        if len(vectors)!=len(facts):
            raise ValueError('Embedding batch length mismatch')
        dimensions={len(v) for v in vectors}
        if facts and (len(dimensions)!=1 or 0 in dimensions):
            raise ValueError('Embedding dimension mismatch')
        for fact,text,vector in zip(facts,texts,vectors):
            if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in vector):
                raise ValueError('Embedding must be finite')
            await self.db.execute('INSERT INTO vectors VALUES(?,?)',(fact.id,json.dumps(vector).encode()))
            await self.db.execute('INSERT INTO facts_fts VALUES(?,?)',(fact.id,text))
            if fact.valid_to is None:
                await self.db.execute('INSERT INTO edges VALUES(?,?,?,?,1) ON CONFLICT(scope,source,target,predicate) DO UPDATE SET weight=weight+1',
                                      (fact.scope,fact.subject,fact.object,fact.predicate))

    async def history(self, subject, predicate, *, scope):
        async with self._transaction():
            return [Fact(**r) for r in await self._rows(
                'SELECT * FROM facts WHERE scope=? AND subject=? AND predicate=? ORDER BY rowid',
                (scope,subject,predicate))]

    async def recall(self, query, *, scope, subject=None, limit=5, include_history=False,
                     fusion_weights=(1.0,1.0,0.5)):
        if len(fusion_weights)!=3 or any(not math.isfinite(w) or w<0 for w in fusion_weights):
            raise ValueError('Three finite nonnegative fusion weights required')
        if limit<=0: return []
        async with self._transaction():
            await self._verify()
            sql='SELECT * FROM facts WHERE scope=?'; args=[clean(scope,'scope')]
            if subject is not None: sql+=' AND subject=?'; args.append(clean(subject,'subject'))
            if not include_history: sql+=' AND valid_to IS NULL'
            sql+=' ORDER BY id'
            facts=[Fact(**r) for r in await self._rows(sql,args)]
            dense=await self._dense_rank(query,facts)
            sparse=await self._sparse_rank(query,facts)
            # Expand only across already scoped candidate facts (no cross-scope graph influence).
            entities={x for f,_ in dense[:3] for x in (f.subject,f.object)}
            graph={f.id:float((f.subject in entities)+(f.object in entities)) for f in facts}
            lists=[dense,sparse,[(f,graph[f.id]) for f in sorted(facts,key=lambda f:(-graph[f.id],f.id)) if graph[f.id]>0]]
            ranks=[{f.id:i for i,(f,_) in enumerate(items,1)} for items in lists]
            ds={f.id:v for f,v in dense}; ss={f.id:v for f,v in sparse}
            results=[RecallResult(f,ds.get(f.id,0),ss.get(f.id,0),
                sum(w/(60+r[f.id]) for w,r in zip(fusion_weights,ranks) if f.id in r),graph[f.id]) for f in facts]
            return sorted(results,key=lambda r:(-r.fused_score,r.fact.id))[:limit]
