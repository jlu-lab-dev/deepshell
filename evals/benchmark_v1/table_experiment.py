"""文件：evals/benchmark_v1/table_experiment.py

职责：对固定 Gold v1.1 在同一知识库索引上对比 Hybrid、Hybrid+Page、
Hybrid+Table、Hybrid+Table+Page；只做检索事实覆盖评测，不调用大模型。
本文件不会修改原始数据集、Chroma 或 GUI。
"""
from __future__ import annotations

import argparse
import hashlib
import ctypes
import json
import platform
import math
import statistics
import time
from datetime import datetime
from pathlib import Path

from evals.benchmark_v1.candidate_diagnostics import score_groups
from rag.table_retrieval import load_facts, table_hybrid_search


ELIGIBLE = {"bound", "preexisting_ids_verified"}
METHODS = {"hybrid", "hybrid_page", "hybrid_table", "hybrid_table_page"}


def p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, int(math.ceil(0.95 * len(ordered))) - 1)
    return round(ordered[index], 2)


def check_hits(rows: list[dict], allowed_ids: list[str], label: str) -> list[str]:
    allowed = set(map(str, allowed_ids))
    ids: list[str] = []
    for row in rows:
        meta = row.get("metadata") or {}
        if str(meta.get("knowledge_base", "")) not in allowed:
            raise RuntimeError(f"{label}: 发现跨知识库检索结果")
        cid = row.get("chroma_id") or meta.get("chunk_id")
        if not cid:
            raise ValueError(f"{label}: 检索结果缺少真实 Chroma ID")
        ids.append(str(cid))
    return ids


def summarize(records: list[dict]) -> dict:
    """明确区别原始检索 Top3 事实覆盖率与 Page 扩展后的上下文事实覆盖率。"""
    ret = {}
    for method in sorted({r["method"] for r in records}):
        subset = [r for r in records if r["method"] == method]
        eligible = [r for r in subset if r["eligible"]]
        def mean(key: str):
            vals = [float(r[key]) for r in eligible if r.get(key) is not None]
            return round(statistics.mean(vals), 4) if vals else None
        cats = {}
        for category in sorted({r["category"] for r in eligible}):
            vals = [r for r in eligible if r["category"] == category]
            cats[category] = {
                "n": len(vals),
                "fact_coverage": round(statistics.mean(r["fact_coverage"] for r in vals), 4),
                "all_facts": round(statistics.mean(r["all_facts"] for r in vals), 4),
            }
        ret[method] = {
            "questions": len(subset), "gold_questions": len(eligible),
            "negative_questions": sum(r.get("task_type", "answerable" if r["eligible"] else "negative") != "answerable" for r in subset),
            "unbound_answerable_questions": sum(r.get("task_type") == "answerable" and not r["eligible"] for r in subset),
            "kb_leak": sum(r["kb_leak"] for r in subset),
            "base_fact_coverage": mean("base_fact_coverage"),
            "base_all_facts": mean("base_all_facts"),
            "base_fact_mrr": mean("base_fact_mrr"),
            "fact_coverage": mean("fact_coverage"),
            "all_facts": mean("all_facts"),
            "fact_mrr": mean("fact_mrr"),
            "p95_retrieval_ms": p95([r["retrieval_ms"] for r in subset]),
            "p95_total_ms": p95([r["total_ms"] for r in subset]),
            "avg_context_chunks": round(statistics.mean(r["context_chunks"] for r in subset), 2),
            "avg_context_chars": round(statistics.mean(r["context_chars"] for r in subset), 2),
            "by_category": cats,
        }
    return ret


def main() -> None:
    ap = argparse.ArgumentParser(description="表格结构化检索 vs 原始 Hybrid + Page")
    ap.add_argument("--dataset", type=Path, default=Path("evals/benchmark_v1/data/enterprise_bound.jsonl"))
    ap.add_argument("--facts", type=Path, default=Path("evals/benchmark_v1/data/table_facts.jsonl"))
    ap.add_argument("--split", choices=("dev", "eval", "all"), default="dev")
    ap.add_argument("--tier", default="explicit")
    ap.add_argument("--category", default="", help="可选：shortcut,runlevel；留空评测全部题型")
    ap.add_argument("--ids", default="", help="可选：用逗号分隔题号")
    ap.add_argument("--methods", default="hybrid,hybrid_page,hybrid_table,hybrid_table_page")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-pages", type=int, default=1)
    ap.add_argument("--max-added-chunks", type=int, default=12)
    ap.add_argument("--max-total-chars", type=int, default=2500)
    ap.add_argument("--output-dir", type=Path, default=Path("evals/benchmark_v1/results/table_dev"))
    args = ap.parse_args()
    selected = list(dict.fromkeys(x.strip() for x in args.methods.split(",") if x.strip()))
    if not selected or set(selected) - METHODS:
        ap.error(f"支持的方法：{sorted(METHODS)}")
    if args.k <= 0:
        ap.error("--k 必须大于0")
    if not args.dataset.is_file():
        ap.error("数据集不存在，请先运行 evals.benchmark_v1.bind_gold")
    questions = [json.loads(line) for line in args.dataset.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    questions = [q for q in questions if (args.split == "all" or q.get("split") == args.split)
                 and (args.tier == "all" or q.get("quality_tier") == args.tier)]
    if args.category:
        categories = {x.strip() for x in args.category.split(",") if x.strip()}
        questions = [q for q in questions if q.get("category") in categories]
    if args.ids:
        wanted = {x.strip() for x in args.ids.split(",") if x.strip()}
        questions = [q for q in questions if q.get("id") in wanted]
    if args.limit > 0:
        questions = questions[:args.limit]
    if not questions:
        ap.error("无匹配问题")
    facts = load_facts(args.facts)
    if platform.system() == "Windows":
        ctypes.WinDLL(r"C:\Windows\System32\MSVCP140.dll")
    from database.repository.knowledge_base_repository import KnowledgeBaseRepository
    from rag.rag_manager import RAGManager
    from rag.page_context import expand_pdf_page_context

    name_to_id = {kb.name: str(kb.id) for kb in KnowledgeBaseRepository().list_knowledge_bases()}
    missing = {kb for q in questions for kb in q["knowledge_bases"]} - set(name_to_id)
    if missing:
        raise RuntimeError(f"缺少知识库：{sorted(missing)}")
    rag = RAGManager()
    records = []
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "details.jsonl").open("w", encoding="utf-8") as details_file:
        for method in selected:
            for idx, q in enumerate(questions, 1):
                allowed_ids = [name_to_id[name] for name in q["knowledge_bases"]]
                start = time.perf_counter()
                if method.startswith("hybrid_table"):
                    base = table_hybrid_search(rag, q["question"], allowed_ids, name_to_id, facts, k=args.k)
                else:
                    base = rag.hybrid_search(q["question"], k=args.k, knowledge_bases=allowed_ids)[:args.k]
                retrieval_ms = (time.perf_counter() - start) * 1000
                initial_ids = check_hits(base, allowed_ids, q["id"])
                expanded = list(base)
                if method.endswith("_page"):
                    expanded = expand_pdf_page_context(
                        vector_db=rag.vector_db, results=expanded, knowledge_bases=allowed_ids,
                        max_pages=args.max_pages, max_added_chunks=args.max_added_chunks,
                        max_total_chars=args.max_total_chars,
                    )
                final_ids = check_hits(expanded, allowed_ids, q["id"])
                eligible = q.get("task_type") == "answerable" and q.get("binding_status") in ELIGIBLE
                initial_metrics = final_metrics = {}
                if eligible:
                    groups = q.get("gold_evidence_groups") or []
                    if not groups:
                        raise ValueError(f"{q['id']} 声称 Gold 绑定成功，但没有证据组")
                    initial_metrics = score_groups(groups, initial_ids, args.k)
                    final_metrics = score_groups(groups, final_ids, len(final_ids))
                elapsed = (time.perf_counter() - start) * 1000
                record = {
                    "id": q["id"], "question": q["question"], "category": q.get("category", "unknown"),
                    "task_type": q["task_type"], "binding_status": q.get("binding_status"),
                    "method": method, "eligible": eligible, "kb_leak": 0,
                    "base_fact_coverage": initial_metrics.get("fact_coverage"),
                    "base_all_facts": initial_metrics.get("all_facts"),
                    "base_fact_mrr": initial_metrics.get("fact_mrr"),
                    "fact_coverage": final_metrics.get("fact_coverage"),
                    "all_facts": final_metrics.get("all_facts"), "fact_mrr": final_metrics.get("fact_mrr"),
                    "retrieval_ms": round(retrieval_ms, 2), "total_ms": round(elapsed, 2),
                    "context_chunks": len(expanded),
                    "context_chars": sum(len(c.get("content") or "") for c in expanded),
                    "table_hit_ids": [c["chroma_id"] for c in base if c.get("table_hit")],
                    "retrieved_chunk_ids": initial_ids,
                    "final_chunk_ids": final_ids,
                    "fact_ranks": final_metrics.get("fact_ranks"),
                }
                records.append(record)
                details_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                details_file.flush()
                print(f"[{method:18} {idx:3}/{len(questions)}] {q['id']}  "
                      f"Fact={final_metrics.get('fact_coverage')}  {elapsed:.1f}ms", flush=True)
    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "dataset": str(args.dataset), "facts": str(args.facts),
        "split": args.split, "tier": args.tier, "k": args.k,
        "category": args.category, "limit": args.limit,
        "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        "facts_sha256": hashlib.sha256(args.facts.read_bytes()).hexdigest(),
        "table_fact_count": len(facts),
        "page_context": {"max_pages": args.max_pages, "max_added_chunks": args.max_added_chunks,
                         "max_total_chars": args.max_total_chars},
        "retrieval_config": {
            "embedding": rag.config.get("embedding", {}).get("local", {}).get("model_name"),
            "chunk_size": rag.config.get("chunk_size"), "chunk_overlap": rag.config.get("chunk_overlap"),
            "hybrid_search": rag.config.get("hybrid_search", {}),
        },
        "methods": summarize(records),
        "note": "只读 Chroma；表格旁路有独立原文事实索引；结果为 Gold Chunk 命中，不等同于最终回答准确率。",
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("[完成]", args.output_dir / "summary.json")
    for name, value in summary["methods"].items():
        print(f"{name:19} Fact={value['fact_coverage']}  All={value['all_facts']}  P95={value['p95_total_ms']}ms")

if __name__ == "__main__":
    main()
