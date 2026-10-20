"""Synthetic Toro workflow. Demonstrates recorded assertions, not mechanical advice."""
import argparse
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from mnemonik import MemoryEngine, Clock

SUBJECT='Toro TimeCutter Zero-Turn'
SCOPE='demo:fleet-01'

async def demonstrate(path):
    if Path(path).exists():
        raise ValueError('Demo requires a new database path; existing data will not be overwritten')
    clock=Clock(1_700_000_000)
    async with MemoryEngine(path,clock=clock) as engine:
        first=await engine.put(SUBJECT,'drive_diagnosis',
            'Left-side drive failure diagnosed as blown hydraulic wheel motor seal.',
            scope=SCOPE,actor='demo:technician-A',evidence='Synthetic initial inspection',expected_id='')
        clock.advance(60)
        corrected=await engine.put(SUBJECT,'drive_diagnosis',
            'Left-side drive failure caused by snapped Wescon lever control cable. Hydraulic system intact.',
            scope=SCOPE,actor='demo:technician-A',evidence='Synthetic follow-up inspection',expected_id=first.id)
        active=await engine.recall('Toro drive failure',scope=SCOPE)
        assert [r.fact.id for r in active]==[corrected.id]
        history=await engine.history(SUBJECT,'drive_diagnosis',scope=SCOPE)
        assert history[0].object==first.object and history[0].valid_to==clock.now()
        assert history[1].supersedes==first.id
        before=await engine.snapshot(); anchor=await engine.verify()
        print('ACTIVE:',active[0].fact.object)
        print('SUPERSEDED:',history[0].object)
    async with MemoryEngine(path,clock=clock) as reopened:
        assert await reopened.snapshot()==before, 'Logical state/index/audit mismatch after restart'
        assert await reopened.verify(anchor['head'])==anchor
        assert [r.fact.id for r in await reopened.recall('Toro drive failure',scope=SCOPE)]==[corrected.id]
    print('PASS: exact logical state, index rows, receipts and retrieval recovered after close/reopen')
    print(json.dumps(anchor,indent=2))

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--db'); args=parser.parse_args()
    if args.db: asyncio.run(demonstrate(args.db))
    else:
        with TemporaryDirectory() as tmp: asyncio.run(demonstrate(str(Path(tmp)/'toro.db')))

if __name__=='__main__': main()
