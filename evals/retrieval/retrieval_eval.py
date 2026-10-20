"""DeepShell：只读 RAG 检索评测入口。

所属模块：evals/retrieval。
职责：基于固定问题集评测 BM25、Chroma 向量检索和当前混合检索，
保存逐题候选及检索延迟；区分页码命中指标与严格 Chunk ID 指标。

不调用 LLM，不写入 Chroma，不重建现有知识库。
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import statistics
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """读取 UTF-8 JSONL，跳过空行。"""
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def file_name(value: Any) -> str:
    """同时兼容 Windows、Unix 路径和裸文件名。"""
    return str(value or "").replace("\\", "/").rsplit("/", 1)[-1].casefold()


def normalize_record(result: dict[str, Any], id_to_name: dict[str, str]) -> dict[str, Any]:
    """规范化 DeepShell 的真实检索结果；PyPDFLoader 页码为零起始。"""
    meta = result.get("metadata") or {}
    page = meta.get("page")
    try:
        page = int(page) + 1 if page is not None else None
        if page is not None and page <= 0:
            page = None
    except (TypeError, ValueError):
        page = None
    kb_id = str(meta.get("knowledge_base", ""))
    chunk_id = str(result.get("chroma_id") or meta.get("chunk_id") or "")
    return {
        "chunk_id": chunk_id,
        "knowledge_base_id": kb_id,
        "knowledge_base_name": id_to_name.get(kb_id, kb_id),
        "source": file_name(meta.get("source")),
        "page": page,
        "score": result.get("score", result.get("bm25_score")),
        "content": str(result.get("content") or "")[:240],
    }


def score_question(question: dict[str, Any], rows: list[dict[str, Any]], k: int) -> dict[str, Any]:
    """只对人工标注提供的指标计分；负例只判知识库泄漏。

    - evidence_page_hit：至少一页参考页出现在检索结果中（宽松定位指标）
    - evidence_page_coverage：所有参考页中，被检索覆盖的比例
    - strict_chunk_hit / strict_chunk_recall / strict_mrr：仅在 gold_chunk_ids 有效时计算

    注意：命中参考页并不保证相应答案句子在返回的 Chunk 中。
    """
    selected = {str(kb) for kb in question.get("knowledge_bases", [])}
    top = rows[:k]
    leaks = [r for r in top if r["knowledge_base_name"] not in selected]
    out: dict[str, Any] = {"kb_leak": bool(leaks), "kb_leak_count": len(leaks)}
    if question.get("task_type") != "answerable":
        return out

    evidence = question.get("evidence") or []
    wanted_pages = {
        (file_name(e.get("source")), int(e["page"]))
        for e in evidence
        if e.get("source") is not None and e.get("page") is not None
    }
    found_pages = {(r["source"], r["page"]) for r in top}
    if wanted_pages:
        matches = wanted_pages & found_pages
        out["evidence_page_hit"] = bool(matches)
        out["evidence_page_coverage"] = len(matches) / len(wanted_pages)
        out["evidence_page_all"] = len(matches) == len(wanted_pages)

    # 未标注 Chunk ID 时，绝对不要编造严格 Recall / MRR。
    gold = {str(x) for x in (question.get("gold_chunk_ids") or [])}
    if gold:
        ranked_ids = [r["chunk_id"] for r in top]
        got = gold & set(ranked_ids)
        out["strict_chunk_hit"] = bool(got)
        out["strict_chunk_recall"] = len(got) / len(gold)
        out["strict_mrr"] = next((1 / (i + 1) for i, rid in enumerate(ranked_ids) if rid in gold), 0.0)
    # 证据组：外层 AND（每个事实都必须命中）；chunk_ids 内层 OR（同一事实任一证据均可）。
    # 不要求每个等价证据 Chunk 都召回，因此这里不使用旧的 strict_chunk_recall。
    groups = question.get("gold_evidence_groups") or []
    if groups:
        ranks = {r["chunk_id"]: i for i, r in enumerate(top, start=1) if r.get("chunk_id")}
        first_ranks = []
        for group in groups:
            alternatives = {str(cid) for cid in group.get("chunk_ids", [])}
            if not alternatives:
                raise ValueError(f"证据组缺少有效 Chunk ID: {question.get('id')}")
            first_ranks.append(min((ranks[cid] for cid in alternatives if cid in ranks), default=None))
        found = sum(rank is not None for rank in first_ranks)
        out["fact_hit"] = found > 0
        out["fact_all"] = found == len(groups)
        out["fact_coverage"] = found / len(groups)
        # 多事实问题取各事实倒数排名的平均，未找到的事实记 0。
        out["fact_mrr"] = sum(1.0 / rank for rank in first_ranks if rank is not None) / len(groups)
    return out


def search_one(rag: Any, method: str, query: str, max_k: int, kb_ids: list[str]) -> list[dict[str, Any]]:
    """调用应用检索接口，保持索引和 Embedding 不变。"""
    if method == "bm25":
        return rag._bm25_search(query, top_k=max_k, knowledge_bases=kb_ids)
    if method == "dense":
        return rag.base_search(query, k=max_k, knowledge_bases=kb_ids)
    if method == "hybrid":
        return rag.hybrid_search(query, k=max_k, knowledge_bases=kb_ids)
    if method == "rrf":
        from rag.rrf_fusion import rrf_fuse
        cfg = rag.config.get("hybrid_search", {})
        # 与 Hybrid 使用一致的两路候选规模，公平比较融合策略。
        bm25 = rag._bm25_search(query, top_k=cfg.get("keyword_top_k", 20), knowledge_bases=kb_ids)
        dense = rag.base_search(query, k=cfg.get("semantic_top_k", 20), knowledge_bases=kb_ids)
        return rrf_fuse([bm25, dense], top_k=max_k, rank_constant=cfg.get("rrf_k", 60))
    if method == "app":
        # 额外用于观察实际聊天的 search() 接口；它可能返回 2*k 个候选。
        return rag.search(query, k=max_k, knowledge_bases=kb_ids)
    raise ValueError(f"未知方法: {method}")


def aggregate(details: list[dict[str, Any]], ks: list[int]) -> list[dict[str, Any]]:
    """按方法和 K 汇总；只统计适用且已标注的指标。"""
    buckets: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for item in details:
        for k in ks:
            buckets[(item["method"], k)].append({
                "task_type": item["task_type"],
                "latency_ms": item["latency_ms"],
                **score_question(item["question"], item["results"], k),
            })

    summary = []
    for (method, k), rows in sorted(buckets.items()):
        answerable = [r for r in rows if r["task_type"] == "answerable"]
        negative = [r for r in rows if r["task_type"] != "answerable"]
        part: dict[str, Any] = {
            "method": method,
            "k": k,
            "questions": len(rows),
            "answerable_questions": len(answerable),
            "negative_questions": len(negative),
            "avg_latency_ms": round(statistics.mean(r["latency_ms"] for r in rows), 2),
            "p95_latency_ms": round(sorted(r["latency_ms"] for r in rows)[max(0, (len(rows) * 95 + 99) // 100 - 1)], 2),
            "kb_leak_queries": sum(r["kb_leak"] for r in rows),
            "negative_kb_leak_queries": sum(r["kb_leak"] for r in negative),
        }
        for metric in ("evidence_page_hit", "evidence_page_all", "evidence_page_coverage", "strict_chunk_hit", "strict_chunk_recall", "strict_mrr", "fact_hit", "fact_all", "fact_coverage", "fact_mrr"):
            values = [r[metric] for r in answerable if metric in r]
            part[metric + "_count"] = len(values)
            part[metric] = round(statistics.mean(values), 4) if values else None
        summary.append(part)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="DeepShell：评测检索基线（不会调用 LLM）")
    parser.add_argument(
        "--dataset", type=Path,
        default=Path("evals/benchmark_v1/data/enterprise_bound.jsonl"),
        help="默认使用正式 Benchmark 的本地 Gold 绑定数据；先运行 bind_gold",
    )
    parser.add_argument("--split", choices=("dev", "eval", "all"), default="dev")
    parser.add_argument("--methods", default="bm25,dense,hybrid", help="可选 bm25,dense,hybrid,rrf,app")
    parser.add_argument("--k", default="3,5,10", help="逗号分隔的 Top-K")
    parser.add_argument("--output-dir", type=Path, default=Path("evals/retrieval/results/baseline"))
    args = parser.parse_args()

    methods = list(dict.fromkeys(x.strip() for x in args.methods.split(",") if x.strip()))
    ks = sorted({int(x.strip()) for x in args.k.split(",") if x.strip()})
    if not ks or min(ks) <= 0:
        parser.error("--k 必须是正整数列表")
    if any(m not in {"bm25", "dense", "hybrid", "rrf", "app"} for m in methods):
        parser.error("--methods 仅支持 bm25,dense,hybrid,rrf,app")

    if not args.dataset.is_file():
        parser.error(f"数据集不存在: {args.dataset}；请先运行 python -m evals.benchmark_v1.bind_gold，或指定 --dataset")
    questions = read_jsonl(args.dataset)
    if args.split != "all":
        questions = [q for q in questions if q.get("split") == args.split]
    if not questions:
        parser.error("数据集没有选定 split 的问题")

    # 兼容此前测试成功的 Windows DLL 加载顺序。
    if platform.system() == "Windows":
        import ctypes
        ctypes.WinDLL(r"C:\Windows\System32\MSVCP140.dll")

    # 延迟导入：只做指标单元测试时，无须加载 Chroma / BGE。
    from database.repository.knowledge_base_repository import KnowledgeBaseRepository
    from rag.rag_manager import RAGManager

    repo = KnowledgeBaseRepository()
    all_kbs = repo.list_knowledge_bases()
    name_to_id = {kb.name: str(kb.id) for kb in all_kbs}
    id_to_name = {str(kb.id): kb.name for kb in all_kbs}
    needed = {name for q in questions for name in q["knowledge_bases"]}
    missing = needed - name_to_id.keys()
    if missing:
        raise RuntimeError(f"先在 GUI 中创建并索引知识库: {sorted(missing)}；当前库: {sorted(name_to_id)}")
    rag = RAGManager()

    details: list[dict[str, Any]] = []
    max_k = max(ks)
    for method in methods:
        for num, question in enumerate(questions, 1):
            kb_ids = [name_to_id[name] for name in question["knowledge_bases"]]
            start = time.perf_counter()
            # 单条失败不应默默当作没有命中；直接中断避免污染评测指标。
            raw = search_one(rag, method, question["question"], max_k, kb_ids)
            latency_ms = round((time.perf_counter() - start) * 1000, 3)
            normalized = [normalize_record(r, id_to_name) for r in raw[:max_k]]
            details.append({
                "id": question["id"],
                "split": question["split"],
                "task_type": question["task_type"],
                "method": method,
                "latency_ms": latency_ms,
                "requested_k": max_k,
                "returned_k": len(normalized),
                "question": question,
                "results": normalized,
            })
            print(f"[{method:6s} {num:02d}/{len(questions)}] {question['id']}  {latency_ms:.0f}ms  {len(normalized)} chunks", flush=True)

    summary = aggregate(details, ks)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path_details = args.output_dir / "retrieval_details.jsonl"
    path_summary = args.output_dir / "summary.json"
    with path_details.open("w", encoding="utf-8") as f:
        for record in details:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    path_summary.write_text(json.dumps({
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "dataset": str(args.dataset),
        "split": args.split,
        "methods": methods,
        "ks": ks,
        "questions": len(questions),
        "embedding_config": rag.config.get("embedding", {}).get("local", {}).get("model_name"),
        "chunk_size": rag.config.get("chunk_size"),
        "chunk_overlap": rag.config.get("chunk_overlap"),
        "hybrid_enabled": rag.config.get("hybrid_search", {}).get("enabled"),
        "note": "页码命中仅是宽松指标；fact_coverage 按 gold_evidence_groups 计分（事实间 AND、组内 Chunk OR），仅对已标注问题统计；未标注不作伪推断。",
        "summary": summary,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n逐题结果：{path_details}\n汇总结果：{path_summary}")
    for item in summary:
        print(f"{item['method']:6s} K={item['k']:2d}  页命中={item['evidence_page_hit']}  "
              f"严格Chunk Recall={item['strict_chunk_recall']}  "
              f"事实覆盖={item['fact_coverage']}  "
              f"KB泄漏={item['kb_leak_queries']}  平均耗时={item['avg_latency_ms']}ms")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    main()
