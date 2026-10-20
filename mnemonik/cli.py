import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from .engine import MemoryEngine

async def run(args):
    if args.command != 'put' and not Path(args.db).is_file():
        raise ValueError('Database does not exist')
    async with MemoryEngine(args.db) as engine:
        if args.command=='put':
            result=asdict(await engine.put(args.subject,args.predicate,args.value,scope=args.scope,
                actor=args.actor,evidence=args.evidence,expected_id=args.expected_id))
        elif args.command=='recall':
            result=[asdict(r) for r in await engine.recall(args.query,scope=args.scope,subject=args.subject,
                        include_history=args.history)]
        elif args.command=='history':
            result=[asdict(f) for f in await engine.history(args.subject,args.predicate,scope=args.scope)]
        elif args.command=='audit':
            result=await engine.verify(args.expected_head)
        else:
            result=await engine.receipts()
        print(json.dumps(result,indent=2,ensure_ascii=False))

def main():
    p=argparse.ArgumentParser(description='MnemonikEvoke offline memory inspector')
    p.add_argument('--db',required=True)
    subs=p.add_subparsers(dest='command',required=True)
    put=subs.add_parser('put')
    for name in ['subject','predicate','value','scope','actor']: put.add_argument('--'+name,required=True)
    put.add_argument('--evidence',default=''); put.add_argument('--expected-id')
    recall=subs.add_parser('recall'); recall.add_argument('query'); recall.add_argument('--scope',required=True)
    recall.add_argument('--subject'); recall.add_argument('--history',action='store_true')
    history=subs.add_parser('history')
    for name in ['subject','predicate','scope']: history.add_argument('--'+name,required=True)
    audit=subs.add_parser('audit'); audit.add_argument('--expected-head')
    subs.add_parser('receipts')
    args=p.parse_args()
    try: asyncio.run(run(args))
    except (ValueError,RuntimeError) as exc: p.exit(1,f'Error: {exc}\n')

if __name__=='__main__': main()
