"""模块：DeepShell 企业 RAG v1.1 两阶段精排对照实验。

文件职责：
- 基于已有 Gold 绑定数据（AND/OR 事实组）对比 BM25、Hybrid、Page、Union-Rerank；
- BM25/Dense 各 Top-N 合并后直接精排，防止 RRF 或 Hybrid 先截断候选；
- 输出逐题有效证据排名、最终覆盖、延迟、上下文字符与知识库泄漏情况。

本脚本不改 GUI / RagManager / 数据集，不调用 Qwen；首次精排会加载 BGE 模型。
"""
from __future__ import annotations

import argparse
import ctypes
import json
import platform
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from evals.benchmark_v1.candidate_diagnostics import (
    ELIGIBLE, _get_search_one, read_jsonl, score_groups,
)
from rag.cross_encoder_reranker import merge_candidates, rerank_with_bge

METHODS = {"bm25", "hybrid", "hybrid_page", "union_rerank", "union_rerank_page"}


def rank_ids(items: list[dict]) -> list[str]:
    """严格提取真实 ID，用于 Gold 命中判断。"""
    out = []
    for item in items:
        meta = item.get("metadata") or {}
        cid = item.get("chroma_id") or meta.get("chunk_id")
        if not cid:
            raise ValueError("候选缺少真实 Chroma ID")
        out.append(str(cid))
    return out


def safe_mean(values: list[float]) -> float | None:
    return round(statistics.mean(values), 4) if values else None


def percentile(values: list[float], q: float) -> float | None:
    """统一以 nearest rank 计算观测分位数，不对小样本外推。"""
    if not values:
        return None
    import math
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * q) - 1)], 4)


def score_or_none(q: dict, items: list[dict]) -> dict | None:
    if q.get("task_type") != "answerable" or q.get("binding_status") not in ELIGIBLE:
        return None
    groups = q.get("gold_evidence_groups") or []
    if not groups:
        raise ValueError(f"{q['id']} 已绑定 Gold，但事实组缺失")
    return score_groups(groups, rank_ids(items), len(items))


def prepare_evidence(rag: Any, method: str, query: str, kb_ids: list[str],
                     *, final_k: int, candidate_k: int, model: str, device: str,
                     batch_size: int, max_pages: int, max_added: int, max_chars: int,
                     search_one: Any) -> tuple[list[dict], list[dict], int, float, float, float]:
    """返回初排前 K、最终证据、并集大小和分阶段耗时。"""
    total_start = time.perf_counter()
    if method.startswith("union_rerank"):
        bm25 = search_one(rag, "bm25", query, candidate_k, kb_ids)[:candidate_k]
        dense = search_one(rag, "dense", query, candidate_k, kb_ids)[:candidate_k]
        merged = merge_candidates(bm25, dense, kb_ids)
        retrieve_ms = (time.perf_counter() - total_start) * 1000
        rerank_start = time.perf_counter()
        original = rerank_with_bge(
            query, merged, top_k=final_k, allowed_kbs=kb_ids,
            model_name=model, device=device, batch_size=batch_size,
        )
        rerank_ms = (time.perf_counter() - rerank_start) * 1000
        pool_size = len(merged)
    else:
        search_method = "bm25" if method == "bm25" else "hybrid"
        original = search_one(rag, search_method, query, final_k, kb_ids)[:final_k]
        retrieve_ms = (time.perf_counter() - total_start) * 1000
        rerank_ms = 0.0
        pool_size = len(original)
    # 页级扩展在 Top-K 截断之后执行。它不是精排收益，单独报告。
    final = list(original)
    expand_start = time.perf_counter()
    if method.endswith("_page"):
        from rag.page_context import expand_pdf_page_context
        final = expand_pdf_page_context(
            rag.vector_db, final, kb_ids, max_pages=max_pages,
            max_added_chunks=max_added, max_total_chars=max_chars,
        )
    expand_ms = (time.perf_counter() - expand_start) * 1000
    # 跨库检索不只是统计指标：评测遇到泄漏直接中断，防止污染后续证据。
    allowed = {str(kb) for kb in kb_ids}
    if any(str((c.get("metadata") or {}).get("knowledge_base", "")) not in allowed for c in final):
        raise RuntimeError("检索或扩展结果跨越了知识库访问范围")
    return original, final, pool_size, retrieve_ms, rerank_ms, expand_ms


def summarize(records: list[dict]) -> dict:
    """按方法单独统计有效 Gold 分母；未调用 LLM，不生成答案准确率。"""
    output: dict[str, Any] = {}
    for method in sorted({r["method"] for r in records}):
        rows = [r for r in records if r["method"] == method]
        gold = [r for r in rows if r["metrics"] is not None]
        times = [r["total_ms"] for r in rows]
        def metric(key: str, layer: str = "metrics") -> dict:
            values = [float(r[layer][key]) for r in gold if r.get(layer) is not None]
            return {"value": safe_mean(values), "n": len(values)}
        categories = sorted({r["category"] for r in gold})
        output[method] = {
            "questions": len(rows), "gold_questions": len(gold),
            "negative_questions": sum(r["task_type"] != "answerable" for r in rows),
            "kb_leak_queries": 0,
            "fact_coverage": metric("fact_coverage"),
            "all_facts": metric("all_facts"),
            "fact_mrr": metric("fact_mrr"),
            "base_fact_coverage": metric("fact_coverage", "base_metrics"),
            "base_all_facts": metric("all_facts", "base_metrics"),
            "base_fact_mrr": metric("fact_mrr", "base_metrics"),
            "avg_candidate_pool": safe_mean([r["candidate_pool_size"] for r in rows]),
            "avg_context_chunks": safe_mean([r["context_chunks"] for r in rows]),
            "avg_context_chars": safe_mean([r["context_chars"] for r in rows]),
            "avg_retrieval_ms": safe_mean([r["retrieval_ms"] for r in rows]),
            "avg_rerank_ms": safe_mean([r["rerank_ms"] for r in rows]),
            "avg_expand_ms": safe_mean([r["expand_ms"] for r in rows]),
            "avg_total_ms": safe_mean(times),
            "p50_total_ms": percentile(times, .5),
            "p95_total_ms": percentile(times, .95),
            "by_category": {category: {
                "n": len(group),
                "fact_coverage": safe_mean([g["metrics"]["fact_coverage"] for g in group]),
            } for category in categories if (group := [r for r in gold if r["category"] == category])},
        }
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="DeepShell 企业 Gold v1.1 精排消融")
    parser.add_argument("--dataset", type=Path, default=Path("evals/benchmark_v1/data/enterprise_bound.jsonl"))
    parser.add_argument("--split", choices=("dev", "eval", "all"), default="dev")
    parser.add_argument("--tier", default="explicit")
    parser.add_argument("--methods", default="bm25,hybrid,hybrid_page,union_rerank,union_rerank_page")
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--candidate-k", type=int, default=20, help="BM25 和 Dense 每路独立候选上限")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--ids", default="")
    parser.add_argument("--model", default="BAAI/bge-reranker-base")
    parser.add_argument("--device", default="cpu", help="cpu 或 cuda")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--max-added-chunks", type=int, default=12)
    parser.add_argument("--max-total-chars", type=int, default=2500)
    parser.add_argument("--output-dir", type=Path, default=Path("evals/benchmark_v1/results/union_rerank_dev"))
    args = parser.parse_args()
    methods = list(dict.fromkeys(x.strip() for x in args.methods.split(",") if x.strip()))
    if not methods or set(methods) - METHODS:
        parser.error(f"--methods 仅支持 {sorted(METHODS)}")
    if args.k <= 0 or args.candidate_k < args.k or args.batch_size <= 0:
        parser.error("--k 必须大于0，--candidate-k不得小于--k，--batch-size须大于0")
    if not args.dataset.exists():
        parser.error("enterprise_bound.jsonl 不存在，请先运行 bind_gold")
    if platform.system() == "Windows":
        ctypes.WinDLL(r"C:\Windows\System32\MSVCP140.dll")
    from database.repository.knowledge_base_repository import KnowledgeBaseRepository
    from rag.rag_manager import RAGManager
    kb_map = {k.name: str(k.id) for k in KnowledgeBaseRepository().list_knowledge_bases()}
    questions = [q for q in read_jsonl(args.dataset)
                 if (args.split == "all" or q.get("split") == args.split)
                 and (args.tier == "all" or q.get("quality_tier") == args.tier)]
    requested = {x.strip() for x in args.ids.split(",") if x.strip()}
    if requested:
        questions = [q for q in questions if q["id"] in requested]
    if args.limit > 0:
        questions = questions[:args.limit]
    if not questions:
        parser.error("没有符合条件的评测题")
    missing = {name for q in questions for name in q["knowledge_bases"]} - set(kb_map)
    if missing:
        raise RuntimeError(f"缺失知识库：{sorted(missing)}")
    search_one = _get_search_one()
    rag = RAGManager()
    # 模型预热不计入单题推理耗时：用合法输入触发一次加载与首轮 forward。
    warmup_ms = 0.0
    if any(m.startswith("union_rerank") for m in methods):
        from rag.cross_encoder_reranker import get_cross_encoder
        print(f"[模型] 加载并预热 {args.model}，设备={args.device}", flush=True)
        warmup_start = time.perf_counter()
        ce = get_cross_encoder(args.model, args.device, 512)
        ce.predict([("查询预热", "预热文档")], batch_size=1, show_progress_bar=False)
        warmup_ms = round((time.perf_counter() - warmup_start) * 1000, 4)
        print(f"[模型] 预热完成，耗时={warmup_ms:.1f}ms", flush=True)
    records = []
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "details.jsonl").open("w", encoding="utf-8") as details_file:
        for method in methods:
            for i, q in enumerate(questions, 1):
                ids = [kb_map[name] for name in q["knowledge_bases"]]
                original, final, pool, retrieve_ms, rerank_ms, expand_ms = prepare_evidence(
                    rag, method, q["question"], ids,
                    final_k=args.k, candidate_k=args.candidate_k,
                    model=args.model, device=args.device, batch_size=args.batch_size,
                    max_pages=args.max_pages, max_added=args.max_added_chunks,
                    max_chars=args.max_total_chars, search_one=search_one,
                )
                metrics = score_or_none(q, final)
                record = {
                    "id": q["id"], "question": q["question"], "category": q.get("category", "unknown"),
                    "task_type": q["task_type"], "method": method,
                    "binding_status": q.get("binding_status"), "metrics": metrics,
                    "base_metrics": score_or_none(q, original),
                    "initial_ids": rank_ids(original), "final_ids": rank_ids(final),
                    "candidate_pool_size": pool, "context_chunks": len(final),
                    "context_chars": sum(len(str(c.get("content") or "")) for c in final),
                    "retrieval_ms": round(retrieve_ms, 4),
                    "rerank_ms": round(rerank_ms, 4),
                    "expand_ms": round(expand_ms, 4),
                    "total_ms": round(retrieve_ms + rerank_ms + expand_ms, 4),
                }
                records.append(record)
                details_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                details_file.flush()
                print(f"[{method:18} {i:03d}/{len(questions)}] {q['id']} "
                      f"候选={pool}  最终={len(final)}  "
                      f"Fact={metrics['fact_coverage'] if metrics else '-'} "
                      f"耗时={record['total_ms']:.1f}ms", flush=True)
    output = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "dataset": str(args.dataset), "split": args.split, "tier": args.tier,
        "k": args.k, "candidate_k_per_channel": args.candidate_k,
        "reranker": {"model": args.model, "device": args.device,
                     "batch_size": args.batch_size, "max_length": 512, "warmup_ms": warmup_ms},
        "page_context": {"max_pages": args.max_pages, "max_added_chunks": args.max_added_chunks,
                         "max_total_chars": args.max_total_chars},
        "retrieval_config": {
            "embedding": rag.config.get("embedding", {}).get("local", {}).get("model_name"),
            "chunk_size": rag.config.get("chunk_size"), "chunk_overlap": rag.config.get("chunk_overlap"),
            "hybrid_search": rag.config.get("hybrid_search", {}),
        },
        "methods": summarize(records),
        "note": "事实组 OR/AND 指标；仅评测检索与扩展，不代表生成回答准确率。",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\n[完成]", args.output_dir / "summary.json")
    for m, item in output["methods"].items():
        print(f"{m:<20} Fact={item['fact_coverage']['value']} "
              f"All={item['all_facts']['value']} "+
              f"平均={item['avg_total_ms']}ms / P95={item['p95_total_ms']}ms")


if __name__ == "__main__":
    main()
