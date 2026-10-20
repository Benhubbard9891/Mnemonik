import asyncio
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from mnemonik import MemoryEngine,Clock,ConflictError,IntegrityError
from mnemonik.providers import AsyncHashingEmbedder

class ReleaseGates(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=str(Path(self.tmp.name)/'memory.db')
        self.clock=Clock(1000); self.engine=await MemoryEngine(self.path,clock=self.clock).setup()
    async def asyncTearDown(self):
        await self.engine.close(); self.tmp.cleanup()
    async def put(self,value='initial',**kwargs):
        args=dict(subject='Toro',predicate='diagnosis',scope='fleet:A',actor='test'); args.update(kwargs)
        return await self.engine.put(value=value,**args)
    async def test_supersession_preserves_original(self):
        a=await self.put(); self.clock.advance(10); b=await self.put('corrected',expected_id=a.id)
        hist=await self.engine.history('Toro','diagnosis',scope='fleet:A')
        self.assertEqual([f.object for f in hist],['initial','corrected'])
        self.assertEqual(hist[0].valid_to,1010); self.assertEqual(b.supersedes,a.id)
        self.assertEqual(len(await self.engine.recall('Toro',scope='fleet:A')),1)
        self.assertEqual((await self.engine.verify())['receipts'],2)
    async def test_scope_and_subject_isolation(self):
        a=await self.put(); b=await self.put('other scope',scope='fleet:B'); c=await self.put('other subject',subject='Deere')
        await self.put('corrected',expected_id=a.id)
        self.assertEqual([r.fact.id for r in await self.engine.recall('diagnosis',scope='fleet:B')],[b.id])
        self.assertEqual([r.fact.id for r in await self.engine.recall('diagnosis',scope='fleet:A',subject='Deere')],[c.id])
        with self.assertRaises(ConflictError): await self.put('wrong',expected_id=b.id)
    async def test_rollback_index_failure(self):
        await self.put(); before=await self.engine.snapshot()
        original=self.engine.embedder.embed_batch
        async def fail(texts): raise RuntimeError('injected after DELETEs')
        self.engine.embedder.embed_batch=fail
        with self.assertRaises(RuntimeError): await self.put('replacement')
        self.assertEqual(await self.engine.snapshot(),before)
        self.engine.embedder.embed_batch=original
        await self.put('recovered'); await self.engine.verify()
    async def test_rollback_receipt_failure(self):
        await self.put(); before=await self.engine.snapshot()
        async def fail(*args): raise RuntimeError('receipt write failure')
        self.engine._append_receipt=fail
        with self.assertRaises(RuntimeError): await self.put('replacement')
        self.assertEqual(await self.engine.snapshot(),before)
    async def test_cancelled_write_rolls_back(self):
        await self.put(); before=await self.engine.snapshot(); entered=asyncio.Event()
        async def pause(texts): entered.set(); await asyncio.Event().wait()
        self.engine.embedder.embed_batch=pause
        task=asyncio.create_task(self.put('replacement')); await entered.wait(); task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertEqual(await self.engine.snapshot(),before)
    async def test_restart_exact_state_and_indexes(self):
        await self.put(); await self.put('corrected'); before=await self.engine.snapshot(); audit=await self.engine.verify()
        await self.engine.close(); self.engine=await MemoryEngine(self.path,clock=self.clock).setup()
        self.assertEqual(await self.engine.snapshot(),before)
        self.assertEqual(await self.engine.verify(audit['head']),audit)
        self.assertEqual((await self.engine.recall('corrected',scope='fleet:A'))[0].fact.object,'corrected')
    async def test_concurrent_stale_update_rejected(self):
        a=await self.put()
        out=await asyncio.gather(self.put('one',expected_id=a.id),self.put('two',expected_id=a.id),return_exceptions=True)
        self.assertEqual(sum(isinstance(x,ConflictError) for x in out),1)
        self.assertEqual((await self.engine.verify())['receipts'],2)
    async def test_independent_connections_serialize(self):
        a=await self.put()
        async with MemoryEngine(self.path,clock=self.clock) as other:
            out=await asyncio.gather(self.put('one',expected_id=a.id),other.put('Toro','diagnosis','two',scope='fleet:A',actor='other',expected_id=a.id),return_exceptions=True)
            self.assertEqual(sum(isinstance(x,ConflictError) for x in out),1)
            await other.verify()
    async def test_noop_audited_without_new_fact(self):
        a=await self.put(); b=await self.put(); self.assertEqual(a.id,b.id)
        self.assertEqual(len((await self.engine.snapshot())['state']['facts']),1)
        self.assertEqual((await self.engine.verify())['receipts'],2)
    async def test_tampered_fact_rejected_on_open(self):
        await self.put(); await self.engine.close()
        with sqlite3.connect(self.path) as db: db.execute("UPDATE facts SET object='tampered'")
        with self.assertRaises(IntegrityError): await self.engine.setup()
    async def test_tampered_index_detected(self):
        await self.put()
        await self.engine.db.execute("DELETE FROM facts_fts")
        with self.assertRaises(IntegrityError): await self.engine.verify()
    async def test_tampered_receipt_detected(self):
        await self.put(); await self.engine.db.execute("UPDATE receipts SET previous_hash='bad'")
        with self.assertRaises(IntegrityError): await self.engine.verify()
    async def test_external_anchor_detects_rollback(self):
        await self.put(); old=await self.engine.verify(); await self.put('new')
        with self.assertRaises(IntegrityError): await self.engine.verify(old['head'])
    async def test_bad_embedding_batch_rolls_back(self):
        await self.put(); before=await self.engine.snapshot()
        async def short(texts): return []
        self.engine.embedder.embed_batch=short
        with self.assertRaises(ValueError): await self.put('bad')
        self.assertEqual(await self.engine.snapshot(),before)
    async def test_clock_regression_rejected(self):
        await self.put(); self.clock._now=999
        with self.assertRaises(ValueError): await self.put('new')
    async def test_process_exit_before_commit(self):
        import subprocess,sys
        await self.put(); before=await self.engine.snapshot(); await self.engine.close()
        code = """
import asyncio,os,sys
from mnemonik import MemoryEngine,Clock
async def main():
    e=await MemoryEngine(sys.argv[1],clock=Clock(1001)).setup()
    async def die(texts): os._exit(73)
    e.embedder.embed_batch=die
    await e.put('Toro','diagnosis','uncommitted',scope='fleet:A',actor='child')
asyncio.run(main())
"""
        result=await asyncio.to_thread(subprocess.run,[sys.executable,'-c',code,self.path],capture_output=True,timeout=15)
        self.assertEqual(result.returncode,73,result.stderr)
        await self.engine.setup()
        self.assertEqual(await self.engine.snapshot(),before)
        await self.engine.verify()
    async def test_restored_old_database_rejected_by_anchor(self):
        backup=str(Path(self.tmp.name)/'older.db')
        await self.put()
        with sqlite3.connect(self.path) as src, sqlite3.connect(backup) as dst: src.backup(dst)
        await self.put('new'); anchor=await self.engine.verify()
        async with MemoryEngine(backup,clock=self.clock) as old:
            with self.assertRaises(IntegrityError): await old.verify(anchor['head'])
    async def test_blank_scope_rejected(self):
        with self.assertRaises(ValueError): await self.put(scope=' ')
    async def test_ranking_guards_and_fts(self):
        await self.put('Wescon cable'); await self.put('hydraulic seal',subject='Deere')
        result=await self.engine.recall('Wescon',scope='fleet:A',fusion_weights=(0,1,0))
        self.assertEqual(result[0].fact.object,'Wescon cable'); self.assertGreater(result[0].sparse_score,0)
        for weights in [(-1,1,1),(float('nan'),1,1)]:
            with self.assertRaises(ValueError): await self.engine.recall('x',scope='fleet:A',fusion_weights=weights)
        result=await self.engine.recall('OR AND NOT',scope='fleet:A')
        self.assertTrue(all(r.fused_score<=2.5/61 for r in result))
    async def test_embedding_dimension_guard(self):
        await self.put(); self.engine.embedder=AsyncHashingEmbedder(32)
        with self.assertRaises(ValueError): await self.engine.recall('Toro',scope='fleet:A')

if __name__=='__main__': unittest.main()
