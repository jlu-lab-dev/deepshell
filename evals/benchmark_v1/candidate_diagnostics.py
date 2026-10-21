"""企业 RAG 基准：粗检索候选召回诊断（不调用 LLM，不改变索引）。

模块职责：
1. 复用 DeepShell 的 BM25 / Dense / Hybrid / RRF 接口，取得 Top-20 候选；
2. 使用已绑定 Gold 事实证据组计算 Fact Coverage@K、All-Facts@K、Fact MRR@K；
3. 区分 Top-3 排名损失和 Top-20 粗召回缺失，保存逐题可追溯结果；
4. 验证知识库边界和 Chroma ID，避免将程序字段缺失误判为检索失败。

注意：Gold 组之间为 AND，每个组中的 chunk_ids 为 OR。
"""
from __future__ import annotations

import argparse
import csv
import ctypes
import importlib
import json
import platform
import statistics
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

def read_jsonl(path: Path) -> list[dict]:
    """独立读取现有绑定数据，不依赖 bind_gold 的运行环境。"""
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


ELIGIBLE = {"bound", "preexisting_ids_verified"}
SUPPORTED = {"bm25", "dense", "hybrid", "rrf"}


def score_groups(groups: list[dict], chunk_ids: list[str], k: int) -> dict:
    """计算前 K 个候选命中的事实数；缺失事实的倒数排名贡献为 0。"""
    if not groups:
        raise ValueError("没有 Gold 事实组，不应计算事实级指标")
    first_rank = {}
    for rank, cid in enumerate(chunk_ids[:k], 1):
        first_rank.setdefault(str(cid), rank)

    ranks = []
    for group in groups:
        alternatives = {str(cid) for cid in group.get("chunk_ids", [])}
        if not alternatives:
            raise ValueError("Gold 事实组为空；请重新执行 bind_gold")
        ranks.append(min((first_rank[cid] for cid in alternatives if cid in first_rank), default=None))

    hits = sum(r is not None for r in ranks)
    return {
        "evidence_hit": hits > 0,
        "fact_coverage": hits / len(groups),
        "all_facts": hits == len(groups),
        "fact_mrr": sum(1 / r for r in ranks if r is not None) / len(groups),
        "fact_ranks": ranks,
    }


def summarize(records: list[dict], ks: list[int]) -> dict:
    """各方法分别报告分母；负例不参与事实覆盖平均值。"""
    output = {}
    for method in sorted({r["method"] for r in records}):
        subset = [r for r in records if r["method"] == method]
        gold = [r for r in subset if r["eligible"]]
        if not gold:
            raise ValueError(f"{method} 没有可评测 Gold 题；检查 --tier / 绑定文件")
        entry = {
            "questions": len(subset),
            "gold_questions": len(gold),
            "negative_questions": sum(r["task_type"] != "answerable" for r in subset),
            "kb_leak_queries": sum(r["kb_leak"] for r in subset),
            "avg_latency_ms": round(statistics.mean(r["latency_ms"] for r in subset), 2),
            "avg_returned_chunks": round(statistics.mean(r["returned_chunks"] for r in subset), 2),
            "by_k": {},
            "by_category_at_max_k": {},
        }
        for k in ks:
            eligible = [r["metrics"][str(k)] for r in gold]
            entry["by_k"][str(k)] = {
                "n": len(eligible),
                "evidence_hit": round(statistics.mean(x["evidence_hit"] for x in eligible), 4),
                "fact_coverage": round(statistics.mean(x["fact_coverage"] for x in eligible), 4),
                "all_facts": round(statistics.mean(x["all_facts"] for x in eligible), 4),
                "fact_mrr": round(statistics.mean(x["fact_mrr"] for x in eligible), 4),
            }
        max_k = str(max(ks))
        categories = sorted({r["category"] for r in gold})
        for cat in categories:
            part = [r["metrics"][max_k] for r in gold if r["category"] == cat]
            entry["by_category_at_max_k"][cat] = {
                "n": len(part),
                "fact_coverage": round(statistics.mean(x["fact_coverage"] for x in part), 4),
                "all_facts": round(statistics.mean(x["all_facts"] for x in part), 4),
            }
        output[method] = entry
    return output


def write_csv(path: Path, rows: list[dict]) -> None:
    """保存 Excel 可直接打开的 UTF-8 BOM 文件。"""
    headers = ["method", "id", "category", "question", "fact_count", "fact_coverage_at_3", "fact_coverage_at_max_k", "ranks_at_max_k"]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in headers})


def select_cases(records: list[dict], ks: list[int]) -> tuple[list[dict], list[dict]]:
    """以全事实命中为准：Top3 未全中，Top20 全中视为排序问题。"""
    small_k = 3
    large_k = max(ks)
    rerankable, recall_missing = [], []
    for r in records:
        if not r["eligible"]:
            continue
        low = r["metrics"][str(small_k)]
        high = r["metrics"][str(large_k)]
        item = {
            "method": r["method"], "id": r["id"],
            "category": r["category"], "question": r["question"],
            "fact_count": r["fact_count"],
            "fact_coverage_at_3": round(low["fact_coverage"], 4),
            "fact_coverage_at_max_k": round(high["fact_coverage"], 4),
            "ranks_at_max_k": json.dumps(high["fact_ranks"], ensure_ascii=False),
        }
        if not low["all_facts"] and high["all_facts"]:
            rerankable.append(item)
        elif not high["all_facts"]:
            recall_missing.append(item)
    return rerankable, recall_missing


def _get_search_one():
    """兼容用户将 evals/day3 重命名为 evals/retrieval 的目录迁移。"""
    for module_name in ("evals.retrieval.retrieval_eval", "evals.day3.retrieval_eval"):
        try:
            module = importlib.import_module(module_name)
            return module.search_one
        except ModuleNotFoundError as exc:
            # 仅允许模块本身不存在时回退；内部依赖缺失必须暴露真实错误。
            if exc.name not in {module_name, module_name.rpartition(".")[0]}:
                raise
    raise RuntimeError("找不到 retrieval_eval.py，请检查 evals/retrieval 或 evals/day3")


def main() -> None:
    parser = argparse.ArgumentParser(description="Top-K Gold 事实证据召回诊断（不调用 LLM）")
    parser.add_argument("--dataset", type=Path, default=Path("evals/benchmark_v1/data/enterprise_bound.jsonl"))
    parser.add_argument("--split", choices=("dev", "eval", "all"), default="dev")
    parser.add_argument("--tier", default="explicit")
    parser.add_argument("--methods", default="bm25,dense,hybrid,rrf")
    parser.add_argument("--k", default="3,5,10,20")
    parser.add_argument("--output-dir", type=Path, default=Path("evals/benchmark_v1/results/candidate_diagnostics"))
    args = parser.parse_args()

    methods = list(dict.fromkeys(m.strip() for m in args.methods.split(",") if m.strip()))
    ks = sorted({int(k.strip()) for k in args.k.split(",") if k.strip()})
    if not methods or set(methods) - SUPPORTED:
        parser.error(f"仅支持 {sorted(SUPPORTED)}")
    if not ks or min(ks) <= 0 or 3 not in ks or max(ks) <= 3:
        parser.error("--k 必须包含 3 和更大的 K，例如 3,5,10,20")
    if not args.dataset.exists():
        parser.error("不存在 enterprise_bound.jsonl，先执行 bind_gold")

    questions = read_jsonl(args.dataset)
    questions = [q for q in questions if (args.split == "all" or q.get("split") == args.split)
                 and (args.tier == "all" or q.get("quality_tier") == args.tier)]
    if not questions:
        parser.error("筛选后没有题目")
    # 不计分的题保留在运行中用于检查跨知识库泄漏；不可计分的回答题必须明确跳过。
    if not any(q.get("task_type") == "answerable" and q.get("binding_status") in ELIGIBLE for q in questions):
        parser.error("缺少已绑定 Gold 事实题")

    if platform.system() == "Windows":
        ctypes.WinDLL(r"C:\Windows\System32\MSVCP140.dll")
    from database.repository.knowledge_base_repository import KnowledgeBaseRepository
    from rag.rag_manager import RAGManager

    kb_map = {kb.name: str(kb.id) for kb in KnowledgeBaseRepository().list_knowledge_bases()}
    missing_kbs = {name for q in questions for name in q["knowledge_bases"]} - set(kb_map)
    if missing_kbs:
        raise RuntimeError(f"知识库不存在：{sorted(missing_kbs)}")
    rag = RAGManager()
    search_one = _get_search_one()
    max_k = max(ks)
    records = []

    for method in methods:
        for i, q in enumerate(questions, 1):
            allowed_ids = {kb_map[name] for name in q["knowledge_bases"]}
            start = time.perf_counter()
            candidates = search_one(rag, method, q["question"], max_k, list(allowed_ids))
            elapsed = round((time.perf_counter() - start) * 1000, 3)
            candidates = candidates[:max_k]
            ranked_ids = []
            kb_leak = False
            for c in candidates:
                meta = c.get("metadata") or {}
                kb_leak |= str(meta.get("knowledge_base", "")) not in allowed_ids
                cid = c.get("chroma_id") or meta.get("chunk_id")
                if not cid:
                    raise RuntimeError(f"{method} / {q['id']} 返回的候选没有真实 Chroma ID，不能计算 Gold 命中")
                ranked_ids.append(str(cid))
            eligible = q.get("task_type") == "answerable" and q.get("binding_status") in ELIGIBLE
            metrics = {}
            if eligible:
                groups = q.get("gold_evidence_groups") or []
                if not groups:
                    raise RuntimeError(f"{q['id']} 已标记为绑定成功，但 gold_evidence_groups 为空")
                metrics = {str(k): score_groups(groups, ranked_ids, k) for k in ks}
            records.append({
                "id": q["id"], "question": q["question"],
                "category": q.get("category", "unknown"), "task_type": q["task_type"],
                "method": method, "eligible": bool(eligible), "kb_leak": bool(kb_leak),
                "latency_ms": elapsed, "returned_chunks": len(candidates),
                "fact_count": len(q.get("gold_evidence_groups") or []) if eligible else 0,
                "metrics": metrics,
                "top_candidates": [
                    {"rank": j, "chunk_id": str(cid), "source": str((c.get("metadata") or {}).get("source", "")),
                     "page": (c.get("metadata") or {}).get("page")}
                    for j, (cid, c) in enumerate(zip(ranked_ids, candidates), 1)
                ],
            })
            print(f"[{method:6} {i:03}/{len(questions)}] {q['id']}   {len(candidates)} chunks   {elapsed:.1f} ms", flush=True)

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "dataset": str(args.dataset), "split": args.split, "tier": args.tier,
        "ks": ks, "top_k": max_k, "methods": summarize(records, ks),
        "note": "只读粗召回诊断；Fact Coverage 按 Gold 事实组 OR/AND 计算，不等于传统相关 Chunk Recall；负例仅用于知识库隔离检查。",
    }
    rerankable, recall_missing = select_cases(records, ks)
    summary["case_counts"] = {"top3_miss_topk_all_hit": len(rerankable), "topk_not_all_hit": len(recall_missing)}

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "details.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8")
    write_csv(args.output_dir / "rerankable_cases.csv", rerankable)
    write_csv(args.output_dir / "recall_missing_cases.csv", recall_missing)
    print("\n[完成]", args.output_dir)
    for method, item in summary["methods"].items():
        print(f"{method:<7} Gold={item['gold_questions']}  Leak={item['kb_leak_queries']}", end="  ")
        print("  ".join(f"Fact@{k}={item['by_k'][str(k)]['fact_coverage']:.2%}" for k in ks))
    print("[排序有提升空间]", len(rerankable), "条方法-题目记录；[Top-K仍缺事实]", len(recall_missing), "条")


if __name__ == "__main__":
    main()
