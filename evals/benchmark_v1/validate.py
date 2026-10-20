"""Benchmark v1 数据集静态校验：ID、split、证据来源和事实组结构。"""
from __future__ import annotations
import argparse
from collections import Counter
from pathlib import Path
from evals.benchmark_v1.bind_gold import read_jsonl


def validate(records: list[dict]) -> dict:
    ids=set();errors=[]
    for q in records:
        qid=q.get('id')
        if not qid or qid in ids:errors.append(f'缺失/重复 ID: {qid}')
        ids.add(qid)
        if q.get('split') not in ('dev','eval'):errors.append(f'{qid}: split 不合法')
        if q.get('task_type') not in ('answerable','negative'):errors.append(f'{qid}: task_type 不合法')
        if not q.get('question'):errors.append(f'{qid}: 无问题文本')
        if not q.get('knowledge_bases'):errors.append(f'{qid}: 无知识库')
        for e in q.get('evidence',[]):
            if 'page' not in e or 'source' not in e:errors.append(f'{qid}: 缺证据页码或来源')
        for g in q.get('gold_evidence_groups') or []:
            if not isinstance(g.get('chunk_ids'),list):errors.append(f'{qid}: Chunk OR 证据格式不合法')
    splits=Counter(r['split'] for r in records)
    cats=Counter(r.get('category') for r in records)
    status=Counter(r.get('binding_status','unbound') for r in records)
    return {'total':len(records),'splits':dict(splits),'categories':dict(cats),
            'binding':dict(status),'errors':errors}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--dataset',type=Path,default=Path('evals/benchmark_v1/data/enterprise_all.jsonl'))
    args=p.parse_args()
    report=validate(read_jsonl(args.dataset))
    print(report)
    if report['errors']:raise SystemExit(1)


if __name__=='__main__':main()
