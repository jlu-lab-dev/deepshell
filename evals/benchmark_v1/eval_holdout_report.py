"""文件：evals/benchmark_v1/eval_holdout_report.py。

模块：DeepShell 企业 RAG 独立 Eval 结果审计。
职责：读取冻结的 Gold 绑定文件及 table_experiment.py 的只读评测结果，
严格区分可评分正例、真实负例及缺少 Gold 的题，统计两种方法逐题改进与退步。
本文件不连接 Chroma、不调用 LLM、不写入原始数据或索引。
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics

BASE = "hybrid_page"
NEW = "hybrid_table_page"
ELIGIBLE = {"bound", "preexisting_ids_verified"}


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(f"未找到文件：{path}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    """保留输入文件指纹，便于证明两轮实验使用同一版标注/事实索引。"""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def percentile95(values: list[float]) -> float | None:
    if not values:
        return None
    values = sorted(values)
    return round(values[math.ceil(len(values) * 0.95) - 1], 2)


def classify_question(question: dict) -> str:
    """不可把 Gold 缺失的可回答题误写为 negative。"""
    if question.get("task_type") == "negative":
        return "negative"
    if question.get("task_type") != "answerable":
        raise ValueError(f"未知任务类型：{question.get('id')}: {question.get('task_type')}")
    groups = question.get("gold_evidence_groups") or []
    if question.get("binding_status") in ELIGIBLE:
        if not groups or any(not group.get("chunk_ids") for group in groups):
            raise ValueError(f"{question['id']} 声称 Gold 已绑定但证据组不完整")
        return "gold"
    return "unbound"


def select_eval(dataset: list[dict], tier: str) -> dict[str, dict]:
    result = {}
    for q in dataset:
        if q.get("split") != "eval" or (tier != "all" and q.get("quality_tier") != tier):
            continue
        if q["id"] in result:
            raise ValueError(f"重复 Eval 题号：{q['id']}")
        result[q["id"]] = q
    if not result:
        raise ValueError("没有符合 split=eval 与 tier 条件的题目")
    return result


def index_details(details: list[dict], question_ids: set[str]) -> dict[str, dict[str, dict]]:
    """保证每种方法都有且仅有一条对应的题目结果，防止漏题后仍算平均。"""
    indexed: dict[str, dict[str, dict]] = {BASE: {}, NEW: {}}
    for rec in details:
        name, qid = rec.get("method"), rec.get("id")
        if name not in indexed:
            raise ValueError(f"不属于本次两方法对照的记录：{name}")
        if qid not in question_ids:
            raise ValueError(f"混入其他数据集的题目：{qid}")
        if qid in indexed[name]:
            raise ValueError(f"重复评测：{name}/{qid}")
        indexed[name][qid] = rec
    for name, mapping in indexed.items():
        missing = question_ids - mapping.keys()
        if missing:
            raise ValueError(f"{name} 缺失 {len(missing)} 道题，示例：{sorted(missing)[:5]}")
    return indexed


def mean(records: list[dict], name: str) -> float | None:
    values = [float(r[name]) for r in records if r.get(name) is not None]
    return round(statistics.mean(values), 6) if values else None


def validate_summary(summary: dict, tier: str, dataset_hash: str, facts_hash: str) -> None:
    """拒绝把旧结果和当前输入拼成一份新的独立测试报告。"""
    if summary.get("split") != "eval" or summary.get("tier") != tier:
        raise ValueError("评测 summary 的 split/tier 不匹配，拒绝混用结果")
    if set(summary.get("methods", {})) != {BASE, NEW}:
        raise ValueError("评测必须恰好包含 hybrid_page、hybrid_table_page 两个方法")
    for key, expected in (("dataset_sha256", dataset_hash), ("facts_sha256", facts_hash)):
        if summary.get(key) != expected:
            raise ValueError(f"评测输入指纹不匹配或缺失：{key}")


def summarize_records(records: list[dict], labels: dict[str, str]) -> dict:
    gold = [rec for rec in records if labels[rec["id"]] == "gold"]
    counts = Counter(labels[rec["id"]] for rec in records)
    return {
        "total_questions": len(records), "gold_questions": len(gold),
        "real_negative_questions": counts["negative"],
        "unbound_answerable_questions": counts["unbound"],
        "fact_coverage": mean(gold, "fact_coverage"),
        "all_facts": mean(gold, "all_facts"), "fact_mrr": mean(gold, "fact_mrr"),
        "kb_leak_queries": sum(bool(rec.get("kb_leak")) for rec in records),
        "p95_total_ms": percentile95([float(rec["total_ms"]) for rec in records]),
        "avg_context_chunks": mean(records, "context_chunks"),
        "avg_context_chars": mean(records, "context_chars"),
    }


def analyze(dataset: list[dict], details: list[dict], tier: str = "explicit") -> dict:
    selected = select_eval(dataset, tier)
    labels = {qid: classify_question(q) for qid, q in selected.items()}
    indexed = index_details(details, set(selected))
    counts = Counter(labels.values())
    tier_counts = Counter(q.get("quality_tier", "unknown") for q in selected.values())

    metric_by_method = {}
    for method, records in indexed.items():
        for qid, rec in records.items():
            expected = labels[qid] == "gold"
            if rec.get("eligible") is not expected:
                raise ValueError(f"{method}/{qid} 的 eligible 与绑定状态不一致")
            fields = ("total_ms", "context_chunks", "context_chars", "kb_leak")
            if expected:
                fields += ("fact_coverage", "all_facts", "fact_mrr")
            for field in fields:
                value = rec.get(field)
                if (not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0
                        or (field in {"fact_coverage", "all_facts", "fact_mrr"} and value > 1)):
                    raise ValueError(f"{method}/{qid} 的 {field} 无效：{value}")
        metric_by_method[method] = summarize_records(list(records.values()), labels)

    pairs = []
    wins, regressions, ties = [], [], []
    for qid, flag in labels.items():
        if flag != "gold":
            continue
        old, new = indexed[BASE][qid], indexed[NEW][qid]
        a, b = float(old["fact_coverage"]), float(new["fact_coverage"])
        delta = round(b - a, 8)
        item = {
            "id": qid, "category": selected[qid].get("category"),
            "tier": selected[qid].get("quality_tier"),
            "baseline_coverage": a, "table_coverage": b,
            "delta": delta,
            "baseline_all_facts": float(old["all_facts"]),
            "table_all_facts": float(new["all_facts"]),
        }
        pairs.append(item)
        if delta > 1e-9:
            wins.append(item)
        elif delta < -1e-9:
            regressions.append(item)
        else:
            ties.append(item)

    def breakdown(field: str) -> dict:
        grouped = defaultdict(list)
        for qid, flag in labels.items():
            grouped[str(selected[qid].get(field, "unknown"))].append(qid)
        return {
            category: {
                "n": sum(labels[qid] == "gold" for qid in ids),
                "total_questions": len(ids),
                "counts": dict(Counter(labels[qid] for qid in ids)),
                "baseline_fact_coverage": mean([indexed[BASE][qid] for qid in ids if labels[qid] == "gold"], "fact_coverage"),
                "table_fact_coverage": mean([indexed[NEW][qid] for qid in ids if labels[qid] == "gold"], "fact_coverage"),
                "methods": {method: summarize_records([indexed[method][qid] for qid in ids], labels)
                            for method in (BASE, NEW)},
                "improved": sum(pair["id"] in ids for pair in wins),
                "regressed": sum(pair["id"] in ids for pair in regressions),
                "unchanged": sum(pair["id"] in ids for pair in ties),
            }
            for category, ids in sorted(grouped.items())
        }

    old_metric, new_metric = metric_by_method[BASE], metric_by_method[NEW]
    return {
        "split": "eval", "tier": tier, "counts": dict(counts),
        "total_questions": len(selected), "tier_counts": dict(tier_counts),
        "methods": metric_by_method,
        "comparison": {
            "fact_coverage_delta_pp": round(100 * (new_metric["fact_coverage"] - old_metric["fact_coverage"]), 2)
            if old_metric["fact_coverage"] is not None and new_metric["fact_coverage"] is not None else None,
            "improved": len(wins), "regressed": len(regressions), "unchanged": len(ties),
            "improved_ids": [q["id"] for q in wins],
            "regressed_ids": [q["id"] for q in regressions],
            "pairs": pairs,
            "by_category": breakdown("category"),
            "by_tier": breakdown("quality_tier"),
        },
        "note": (
            "Fact Coverage 是已有 Gold 证据的检索覆盖率（逐题宏平均）；"
            "真实负例单独计数，Gold 缺失题不得混入负例；"
            "Silver 尚待人工复核，未测量 Qwen 回答准确率。"
        ),
    }


def to_markdown(result: dict) -> str:
    """生成可提交实验报告摘要，但不会虚构尚未完成的指标。"""
    metric = result["methods"]
    a, b = metric[BASE], metric[NEW]
    display_pct = lambda x: "N/A" if x is None else f"{x * 100:.2f}%"
    display_num = lambda x: "N/A" if x is None else f"{x:.2f}"
    display_mrr = lambda x: "N/A" if x is None else f"{x:.4f}"
    comp = result["comparison"]
    lines = [
        "# DeepShell 独立 Eval 检索验证报告", "",
        f"- 数据集：`eval` / `{result['tier']}`，共 **{result['total_questions']}** 道题",
        f"- 有效 Gold：**{result['counts'].get('gold', 0)}** 道；真实负例：**{result['counts'].get('negative', 0)}** 道；未绑定 Gold 的可回答题：**{result['counts'].get('unbound', 0)}** 道",
        "- 注意：Silver 仅为待人工审核的标注；本报告是证据检索验证，不是最终回答准确率。", "",
        "| 指标 | Hybrid+Page | Hybrid+Table+Page |", "|---|---:|---:|",
        f"| Fact Coverage | {display_pct(a['fact_coverage'])} | {display_pct(b['fact_coverage'])} |",
        f"| All-Facts | {display_pct(a['all_facts'])} | {display_pct(b['all_facts'])} |",
        f"| Fact MRR | {display_mrr(a['fact_mrr'])} | {display_mrr(b['fact_mrr'])} |",
        f"| P95 总耗时 | {display_num(a['p95_total_ms'])} ms | {display_num(b['p95_total_ms'])} ms |",
        f"| 知识库泄漏题数 | {a['kb_leak_queries']} | {b['kb_leak_queries']} |", "",
        f"- Fact Coverage 差值：**{comp['fact_coverage_delta_pp']} 个百分点**",
        f"- 逐题事实覆盖改善：**{comp['improved']}** 题；退步：**{comp['regressed']}** 题；持平：**{comp['unchanged']}** 题",
        "", "## 按标注质量分层", "",
        "| 层级 | 总题数 | Gold | 真实负例 | 缺少 Gold | 基线覆盖率 | 表格覆盖率 | 改善 / 退步 / 持平 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for tier, group in comp["by_tier"].items():
        counts = group["counts"]
        lines.append(f"| {tier} | {group['total_questions']} | {counts.get('gold', 0)} | "
                     f"{counts.get('negative', 0)} | {counts.get('unbound', 0)} | "
                     f"{display_pct(group['baseline_fact_coverage'])} | {display_pct(group['table_fact_coverage'])} | "
                     f"{group['improved']} / {group['regressed']} / {group['unchanged']} |")
    lines.extend([
        "", "## 解释", "",
        "主结论以 Explicit 为准；全部 Eval 的合并指标仅作参考，各层详细指标保存在 JSON 中。",
        "Top-3 为同页扩展前的检索数量；事实指标在扩展后的全部上下文中评分。",
        "独立 Eval 仅检验冻结后的方法在未参与调参的题目上是否保持性能。",
        "由于两份手册与已人工核验的两张表在 Dev 和 Eval 之间共享，它不是跨文档或跨表格泛化测试。",
        "真实负例的 KB 隔离成功不代表生成模型必然拒答。", "",
    ])
    if result.get("source_hashes"):
        lines.extend(["## 输入与结果指纹", ""])
        lines.extend(f"- {key}: `{value}`" for key, value in result["source_hashes"].items())
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="只读地审计 DeepShell 独立 Eval 两方法结果")
    ap.add_argument("--dataset", type=Path, default=Path("evals/benchmark_v1/data/enterprise_bound.jsonl"))
    ap.add_argument("--result-dir", type=Path, default=Path("evals/benchmark_v1/results/table_eval_explicit"))
    ap.add_argument("--tier", choices=("explicit", "silver", "legacy", "all"), default="explicit")
    ap.add_argument("--facts", type=Path, default=Path("evals/benchmark_v1/data/table_facts.jsonl"))
    ap.add_argument("--check-only", action="store_true", help="仅检查题数、Gold 状态和输入指纹，不需要评测结果")
    args = ap.parse_args()
    data = read_jsonl(args.dataset)
    selected = select_eval(data, args.tier)
    counts = Counter(classify_question(q) for q in selected.values())
    print(f"[预检查] Eval tier={args.tier}, 总计={len(selected)}, Gold={counts['gold']}, "
          f"真实负例={counts['negative']}, 待绑定={counts['unbound']}")
    print(f"[指纹] Gold SHA256: {sha256(args.dataset)}")
    if args.facts.is_file():
        print(f"[指纹] Table Facts SHA256: {sha256(args.facts)}")
    else:
        raise FileNotFoundError(f"没有找到表格事实索引：{args.facts}")
    if args.check_only:
        return

    summary_file = args.result_dir / "summary.json"
    summary = json.loads(summary_file.read_text(encoding="utf-8"))
    validate_summary(summary, args.tier, sha256(args.dataset), sha256(args.facts))
    rows = read_jsonl(args.result_dir / "details.jsonl")
    result = analyze(data, rows, args.tier)
    result["created_at"] = datetime.now().isoformat(timespec="seconds")
    result["source_hashes"] = {"dataset_sha256": sha256(args.dataset), "table_facts_sha256": sha256(args.facts),
                               "summary_sha256": sha256(summary_file),
                               "details_sha256": sha256(args.result_dir / "details.jsonl")}
    result["experiment"] = {key: summary.get(key) for key in
                            ("created_at", "k", "page_context", "retrieval_config", "table_fact_count")}
    out_json = args.result_dir / "holdout_report.json"
    out_md = args.result_dir / "holdout_report.md"
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(to_markdown(result), encoding="utf-8")
    print(f"[完成] {out_md}")
    print(to_markdown(result))


if __name__ == "__main__":
    main()
