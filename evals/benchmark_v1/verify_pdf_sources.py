"""可选：用本地 PDF 原件核验发布版 Benchmark 的来源页码和原文锚点。

用法：python -m evals.benchmark_v1.verify_pdf_sources --desktop "...pdf" --server "...pdf"
用途：检查 PDF 版本、页码和自动标注的片段存在性，不宣称验证了语义问答正确性。
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from evals.benchmark_v1.bind_gold import read_jsonl


def norm(text: str) -> str:
    return re.sub(r'\s+', '', text).casefold()


def main():
    p=argparse.ArgumentParser(description='检查原始 PDF SHA256、证据页和 quote 是否匹配')
    p.add_argument('--desktop',type=Path,required=True)
    p.add_argument('--server',type=Path,required=True)
    p.add_argument('--dataset',type=Path,default=Path('evals/benchmark_v1/data/enterprise_all.jsonl'))
    args=p.parse_args()
    try:
        import fitz
    except ImportError:
        fitz = None
        from pypdf import PdfReader
    sources={'KB_A_Desktop_V5':args.desktop,'KB_B_Server_V4':args.server}
    manifest=json.loads((Path(__file__).resolve().parent/'data'/'manifest.json').read_text(encoding='utf-8'))
    docs={};hash_mismatches=[]
    for m in manifest['source_pdfs']:
        pth=sources[m['knowledge_base']]
        digest=hashlib.sha256(pth.read_bytes()).hexdigest()
        print(m['knowledge_base'], 'SHA256 一致' if digest==m['sha256'] else 'SHA256 不同，谨慎使用')
        if digest!=m['sha256']:hash_mismatches.append(m['knowledge_base'])
        docs[m['knowledge_base']]=fitz.open(pth) if fitz is not None else PdfReader(pth)
    checked=0;missing=[]
    for row in read_jsonl(args.dataset):
        doc=docs[row['knowledge_bases'][0]]
        for e in row.get('evidence',[]):
            if not e.get('quote'):continue
            pg=int(e['page'])
            checked+=1
            count=len(doc) if fitz is not None else len(doc.pages)
            text=(doc[pg-1].get_text() if fitz is not None else doc.pages[pg-1].extract_text() or '') if 1<=pg<=count else ''
            if not 1<=pg<=count or norm(e['quote']) not in norm(text):
                missing.append({'id':row['id'],'page':pg,'quote':e['quote']})
    print(f'来源锚点检查 {checked} 个，失败 {len(missing)} 个')
    for doc in docs.values():doc.close()
    if missing:
        print(json.dumps(missing[:20],ensure_ascii=False,indent=2))
        raise SystemExit(1)
    if hash_mismatches:raise SystemExit(1)


if __name__=='__main__':main()
