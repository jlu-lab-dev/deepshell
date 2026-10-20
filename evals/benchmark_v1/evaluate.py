"""Enterprise Benchmark v1：复用公共检索、页级扩展和生成评测，提供分层统计。

文件职责：
- 只读取已绑定的数据，按 split、质量层、方法执行离线评测；
- 保留每题的原始/扩展后证据、检索耗时、可选模型生成结果；
- 把银标与明确证据题分开统计，防止 200+ 自动样本夸大结论。

运行前先 `python -m evals.benchmark_v1.bind_gold`。
"""
from __future__ import annotations

import argparse
import ctypes
import json
import platform
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from evals.benchmark_v1.bind_gold import read_jsonl, dump_jsonl


def avg(values: list[float]) -> float | None:
    return round(statistics.mean(values), 4) if values else None


def summarize(rows: list[dict]) -> dict:
    """显式返回各指标分母，拒绝把未标注 Gold 的样本算作 0。"""
    output: dict[str, Any] = {"total":len(rows),"methods":{}}
    for method in sorted({r["method"] for r in rows}):
        records = [r for r in rows if r["method"]==method]
        eligible = [r for r in records if r.get("binding_status") in
                    {"bound", "preexisting_ids_verified"} and r["task_type"]=="answerable"]
        # 旧 UUID 经验证存在后也可统计，但单独显示人数；语义支持仍应人工核验。
        trustworthy = list(eligible)
        neg = [r for r in records if r["task_type"]!="answerable"]
        def metric(name: str, qualified: list[dict], layer: str="final_metrics"):
            values=[float(r[layer][name]) for r in qualified if name in r.get(layer,{}) and isinstance(r[layer][name],(bool,int,float))]
            return {"value":avg(values),"n":len(values)}
        output["methods"][method]={
            "questions":len(records),
            "verified_bound_questions":len(trustworthy),
            "verified_legacy_questions":sum(r["binding_status"]=="preexisting_ids_verified" for r in eligible),
            "unbound_answerable_questions":sum(r["task_type"]=="answerable" and r["binding_status"] not in {"bound","preexisting_ids_verified"} for r in records),
            "negative_questions":len(neg),
            "base_kb_leak_queries":sum(bool(r.get("base_metrics",{}).get("kb_leak")) for r in records),
            "kb_leak_queries":sum(bool(r.get("final_metrics",{}).get("kb_leak")) for r in records),
            "negative_kb_leak_queries":sum(bool(r.get("final_metrics",{}).get("kb_leak")) for r in neg),
            "base_fact_coverage":metric("fact_coverage",trustworthy,"base_metrics"),
            "final_fact_coverage":metric("fact_coverage",trustworthy),
            "base_all_facts":metric("fact_all",trustworthy,"base_metrics"),
            "final_all_facts":metric("fact_all",trustworthy),
            "final_fact_mrr":metric("fact_mrr",trustworthy),
            "negative_abstain_heuristic":metric("negative_abstain_heuristic",records,"generation_metrics"),
            "citation_ids_valid":metric("citation_ids_valid",records,"generation_metrics"),
            "answer_fact_coverage_heuristic":metric("answer_fact_coverage_heuristic",records,"generation_metrics"),
            "avg_retrieval_ms":avg([r["retrieval_ms"] for r in records]),
            "avg_expand_ms":avg([r["expand_ms"] for r in records]),
            "avg_context_chunks":avg([r["context_chunks"] for r in records]),
            "avg_context_chars":avg([r["context_chars"] for r in records]),
            "avg_generation_ms":avg([r["generation_ms"] for r in records if "generation_ms" in r]),
            "by_category":{
                cat:{"n":len(rs),"final_fact_coverage":metric("fact_coverage",[r for r in rs if r["binding_status"] in {"bound","preexisting_ids_verified"}])}
                for cat in sorted({r["category"] for r in records})
                if (rs:=[r for r in records if r["category"]==cat])
            },
        }
    tiers = sorted({r.get("quality_tier", "unknown") for r in rows})
    output["quality_tiers"] = tiers
    if len(tiers) > 1:
        output["by_quality_tier"] = {
            tier: summarize([r for r in rows if r.get("quality_tier", "unknown") == tier])
            for tier in tiers
        }
    return output


def main() -> None:
    p=argparse.ArgumentParser(description="DeepShell 正式企业 RAG 分层基准")
    p.add_argument("--dataset",type=Path,default=Path("evals/benchmark_v1/data/enterprise_bound.jsonl"))
    p.add_argument("--split",choices=("dev","eval","all"),default="dev")
    p.add_argument("--tier",default="explicit",help="explicit,silver,legacy 或 all；默认只测来源直接问答及参数题")
    p.add_argument("--methods",default="hybrid,rrf,hybrid_page,rrf_page")
    p.add_argument("--k",type=int,default=3)
    p.add_argument("--limit",type=int,default=0)
    p.add_argument("--ids",default="")
    p.add_argument("--max-pages",type=int,default=1)
    p.add_argument("--max-added-chunks",type=int,default=12)
    p.add_argument("--max-total-chars",type=int,default=2500)
    p.add_argument("--llm-model",default="",help="可选 Qwen-FLASH；为空只测检索，不产生 API 费用")
    p.add_argument("--direct-api",action="store_true",help="仅本次 OpenAI 兼容模型调用忽略系统代理，保留 TLS 证书验证")
    p.add_argument("--output-dir",type=Path,default=Path("evals/benchmark_v1/results/dev_explicit"))
    args=p.parse_args()
    if not args.dataset.exists():p.error("尚无绑定后的数据集。请先执行 python -m evals.benchmark_v1.bind_gold")
    questions=read_jsonl(args.dataset)
    tier=set(t.strip() for t in args.tier.split(","))
    if tier!={"all"}:questions=[q for q in questions if q.get("quality_tier") in tier]
    if args.split!="all":questions=[q for q in questions if q.get("split")==args.split]
    wanted={x.strip() for x in args.ids.split(",") if x.strip()}
    if wanted:questions=[q for q in questions if q["id"] in wanted]
    if args.limit>0:questions=questions[:args.limit]
    if not questions:p.error("当前筛选后没有题目")
    methods=list(dict.fromkeys(x.strip() for x in args.methods.split(",") if x.strip()))
    supported={"hybrid","rrf","hybrid_page","rrf_page"}
    if not methods or any(m not in supported for m in methods):p.error(f"只支持 {sorted(supported)}")
    if args.k<=0:p.error("--k 必须 > 0")
    if platform.system()=="Windows":ctypes.WinDLL(r"C:\Windows\System32\MSVCP140.dll")
    from database.repository.knowledge_base_repository import KnowledgeBaseRepository
    from rag.rag_manager import RAGManager
    from evals.retrieval.pipeline_eval import run_one, load_llm
    repo=KnowledgeBaseRepository()
    kbs=repo.list_knowledge_bases()
    name_to_id={kb.name:str(kb.id) for kb in kbs}
    id_to_name={str(kb.id):kb.name for kb in kbs}
    missing={n for q in questions for n in q["knowledge_bases"]} - set(name_to_id)
    if missing:raise RuntimeError(f"缺少知识库 {sorted(missing)}")
    rag=RAGManager()
    llm=load_llm(args.llm_model,direct_api=args.direct_api) if args.llm_model else None
    records=[]
    args.output_dir.mkdir(parents=True,exist_ok=True)
    with (args.output_dir/"details.jsonl").open("w",encoding="utf-8") as details_file:
        for method in methods:
            for i,q in enumerate(questions,1):
                ids=[name_to_id[name] for name in q["knowledge_bases"]]
                res=run_one(rag,q,method,ids,id_to_name,args.k,args.max_pages,args.max_added_chunks,args.max_total_chars,llm)
                res["quality_tier"]=q["quality_tier"]
                res["category"]=q["category"]
                res["binding_status"]=q.get("binding_status","not_bound")
                records.append(res)
                details_file.write(json.dumps(res,ensure_ascii=False)+"\n")
                details_file.flush()
                print(f"[{method:11} {i:03d}/{len(questions)}] {q['id']}  chunks={res['context_chunks']}  {res['retrieval_ms']}ms",flush=True)
    stats=summarize(records)
    stats["created_at"]=datetime.now().isoformat(timespec="seconds")
    stats["data_file"]=str(args.dataset)
    stats["split"]=args.split
    stats["tier"]=args.tier
    stats["k"]=args.k
    stats["llm_model"]=args.llm_model or None
    stats["direct_api"]=args.direct_api
    stats["page_context"]={"max_pages":args.max_pages,"max_added_chunks":args.max_added_chunks,"max_total_chars":args.max_total_chars}
    stats["retrieval_config"]={
        "embedding":rag.config.get("embedding",{}).get("local",{}).get("model_name"),
        "chunk_size":rag.config.get("chunk_size"),"chunk_overlap":rag.config.get("chunk_overlap"),
        "keyword_top_k":rag.config.get("hybrid_search",{}).get("keyword_top_k",20),
        "semantic_top_k":rag.config.get("hybrid_search",{}).get("semantic_top_k",20),
        "rrf_k":rag.config.get("hybrid_search",{}).get("rrf_k",60),
    }
    stats["warning"]="全部质量层均需区分；Silver 属于待人工复核，quote 匹配不是语义真值。生成启发式不等于忠实性。"
    (args.output_dir/"summary.json").write_text(json.dumps(stats,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("[完成]",args.output_dir/"summary.json")
    for m,part in stats["methods"].items():
        print(m,"Gold证据题:",part["verified_bound_questions"],
              "原始FactCoverage:",part["base_fact_coverage"],
              "扩展FactCoverage:",part["final_fact_coverage"],
              "平均上下文字符:",part["avg_context_chars"])


if __name__=="__main__":main()
