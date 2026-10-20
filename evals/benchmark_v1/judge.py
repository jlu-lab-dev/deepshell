"""Enterprise Benchmark v1 可选 LLM-as-a-Judge（独立运行，避免重复检索）。

用途：对 `evaluate.py --llm-model ...` 的详细日志按题评分。
职责：给出答案准确性、忠实性、引用支持度、拒答质量，以及每项解释。
局限：模型评委并非真值；必须抽样人工核查并报告一致率；Silver 仍待复核。
"""
from __future__ import annotations
import argparse
import ctypes
import json
import platform
import re
import statistics
from pathlib import Path
from typing import Any
from evals.benchmark_v1.bind_gold import read_jsonl, dump_jsonl

RUBRIC = '''你是独立 RAG 评测员。只依据给出的【问题】【参考答案】【实际提供给生成模型的证据】【生成答案】评分。
请输出一个严格 JSON 对象，不能输出 Markdown、额外文字或推测。
要求：
- answer_correctness: 0..1，内容是否正确回答问题；参考答案可能只是摘录，不应强制逐字一致。
- faithfulness: 0..1，答案的实质断言能否由【实际证据】推出；没有证据但编造则低分。
- citation_support: 0..1，答案中的引用编号是否支持对应断言；若无引用且本应引用，给 0。
- abstention_quality: 0..1，如果所选文档没有必要证据，是否合理拒答；对可以回答的问题始终给 null。
- reason: 用中文简述扣分依据及对应的证据编号。
无有效证据时不可使用常识替证据辩护。按评分原则不要因措辞不同惩罚正确回答。
JSON 必须包含上述5个字段。'''


def parse_grade(raw: str) -> dict[str,Any]:
    """验证模型输出，不合法则报错，不能把失败解析当作 0 分。"""
    s=str(raw).strip()
    if s.startswith('```'):
        s=re.sub(r'^```(?:json)?\s*|\s*```$', '', s).strip()
    obj=json.loads(s)
    if not isinstance(obj,dict):raise ValueError('评委返回的不是 JSON 对象')
    for k in ('answer_correctness','faithfulness','citation_support'):
        v=obj.get(k)
        if not isinstance(v,(int,float)) or isinstance(v,bool) or not 0<=v<=1:
            raise ValueError(f'{k} 必须是 0..1，收到 {v!r}')
    v=obj.get('abstention_quality')
    if v is not None and (not isinstance(v,(int,float)) or isinstance(v,bool) or not 0<=v<=1):
        raise ValueError('abstention_quality 必须是 null 或 0..1')
    if not isinstance(obj.get('reason'),str):raise ValueError('reason 必须是字符串')
    return obj


def prompt_for(row:dict[str,Any]) -> str:
    evid='\n\n'.join(f"[{i}] {e['source']} 第{e['page']}页，Chunk ID={e['chunk_id']}\n{e['content']}"
                         for i,e in enumerate(row['evidence'],1))
    return (f"【题目】{row['question']}\n【题型】{row['task_type']}\n"
            f"【参考答案（可能有人工复核风险）】{row.get('reference_answer') or '无'}\n"
            f"【实际证据】\n{evid or '（没有检索到）'}\n"
            f"【生成答案】\n{row['answer']}\n")


def summarize_judgments(results: list[dict]) -> dict:
    """保留评分分母及错误数；拒答分只统计明确标记的负例。"""
    summary = {}
    for method in sorted({r['method'] for r in results}):
        rows = [r for r in results if r['method'] == method]
        valid = [r for r in rows if 'error' not in r['judge']]
        part = {'judged': len(valid), 'errors': len(rows) - len(valid)}
        for metric in ('answer_correctness', 'faithfulness', 'citation_support', 'abstention_quality'):
            applicable = valid
            if metric == 'abstention_quality':
                applicable = [r for r in valid if r.get('task_type') in {'negative', 'cross_kb_unanswerable'}]
            values = [float(r['judge'][metric]) for r in applicable
                      if isinstance(r['judge'].get(metric), (int, float))
                      and not isinstance(r['judge'][metric], bool)]
            part[metric] = {'value': round(statistics.mean(values), 4) if values else None, 'n': len(values)}
        summary[method] = part
    return summary


def main() -> None:
    p=argparse.ArgumentParser(description='基于实际生成答案进行 Qwen Judge 评测，需 API 费用')
    p.add_argument('--details',type=Path,required=True)
    p.add_argument('--judge-model',required=True)
    p.add_argument('--direct-api',action='store_true',help='仅本次 OpenAI 兼容调用忽略系统代理，保留 TLS 验证')
    p.add_argument('--limit',type=int,default=0)
    p.add_argument('--output-dir',type=Path,default=Path('evals/benchmark_v1/results/judge'))
    args=p.parse_args()
    records=[r for r in read_jsonl(args.details) if r.get('answer')]
    if args.limit>0:records=records[:args.limit]
    if not records:raise SystemExit('没有任何生成答案；请先在 evaluate 中使用 --llm-model')
    if platform.system()=='Windows':ctypes.WinDLL(r'C:\Windows\System32\MSVCP140.dll')
    from langchain_core.messages import HumanMessage, SystemMessage
    from evals.retrieval.pipeline_eval import load_llm, extract_answer
    llm=load_llm(args.judge_model,direct_api=args.direct_api)
    results=[]
    for ix,row in enumerate(records,1):
        try:
            result=llm.invoke([SystemMessage(content=RUBRIC),HumanMessage(content=prompt_for(row))])
            grade=parse_grade(extract_answer(result)[0])
        except Exception as exc:
            grade={'error':str(exc)}
        results.append({'id':row['id'],'method':row['method'],'quality_tier':row['quality_tier'],
                        'category':row['category'],'task_type':row['task_type'],'judge':grade})
        print(f"[{ix}/{len(records)}] {row['method']} {row['id']} {grade}",flush=True)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    dump_jsonl(args.output_dir/'judge_details.jsonl',results)
    summary=summarize_judgments(results)
    (args.output_dir/'summary.json').write_text(json.dumps({'methods':summary,'warning':'自动评委仅做实验代理；需要人工标注核对。'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('[完成]',args.output_dir/'summary.json')


if __name__=='__main__':main()
