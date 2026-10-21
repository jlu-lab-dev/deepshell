"""文件：evals/benchmark_v1/tests/test_eval_holdout_report.py。
模块：独立 Eval 统计正确性回归测试；不触碰任何真实 Chroma 索引。
"""
import unittest

from evals.benchmark_v1.eval_holdout_report import (
    analyze, classify_question, index_details, select_eval, to_markdown, validate_summary,
)


def q(id_, kind, status, tier="explicit"):
    return {"id": id_, "split": "eval", "quality_tier": tier,
            "category": "faq", "task_type": kind, "binding_status": status,
            "gold_evidence_groups": [{"chunk_ids": ["ch1"]}] if status == "bound" else []}


def record(id_, method, eligible, score=None, leak=0):
    return {"id": id_, "method": method, "eligible": eligible, "fact_coverage": score,
            "all_facts": score, "fact_mrr": score, "kb_leak": leak, "total_ms": 10,
            "context_chunks": 3, "context_chars": 120}


class EvalAuditTests(unittest.TestCase):
    def test_real_negative_is_different_from_missing_gold(self):
        self.assertEqual(classify_question(q("n", "negative", "not_applicable")), "negative")
        self.assertEqual(classify_question(q("u", "answerable", "no_source_anchor")), "unbound")

    def test_verified_gold(self):
        self.assertEqual(classify_question(q("g", "answerable", "bound")), "gold")

    def test_stale_gold_group_detected(self):
        data = q("g", "answerable", "bound")
        data["gold_evidence_groups"] = []
        with self.assertRaises(ValueError):
            classify_question(data)

    def test_only_eval_is_selected(self):
        data = [q("a", "answerable", "bound"), q("b", "answerable", "bound", "silver")]
        other = q("c", "answerable", "bound")
        other["split"] = "dev"
        self.assertEqual(set(select_eval(data + [other], "explicit")), {"a"})
        self.assertEqual(set(select_eval(data + [other], "all")), {"a", "b"})

    def test_missing_method_question_rejected(self):
        with self.assertRaises(ValueError):
            index_details([record("g", "hybrid_page", True, 1.0)], {"g"})

    def test_report_counts_and_improvement(self):
        data = [q("g1", "answerable", "bound"), q("g2", "answerable", "bound"),
                q("neg", "negative", "not_applicable"), q("unknown", "answerable", "no_source_anchor")]
        rows = []
        for method in ("hybrid_page", "hybrid_table_page"):
            rows += [record("g1", method, True, 0 if method == "hybrid_page" else 1),
                     record("g2", method, True, 1), record("neg", method, False),
                     record("unknown", method, False)]
        out = analyze(data, rows)
        self.assertEqual(out["counts"], {"gold": 2, "negative": 1, "unbound": 1})
        self.assertEqual(out["comparison"]["improved"], 1)
        self.assertEqual(out["comparison"]["fact_coverage_delta_pp"], 50.0)
        self.assertEqual(out["methods"]["hybrid_page"]["gold_questions"], 2)
        self.assertEqual(out["methods"]["hybrid_page"]["real_negative_questions"], 1)

    def test_report_regression_detected(self):
        data = [q("g", "answerable", "bound")]
        rows = [record("g", "hybrid_page", True, 1),
                record("g", "hybrid_table_page", True, 0)]
        self.assertEqual(analyze(data, rows)["comparison"]["regressed_ids"], ["g"])

    def test_eligible_mismatch_rejected(self):
        data = [q("g", "answerable", "bound")]
        rows = [record("g", "hybrid_page", False, 0),
                record("g", "hybrid_table_page", True, 1)]
        with self.assertRaises(ValueError):
            analyze(data, rows)

    def test_duplicate_record_rejected(self):
        with self.assertRaises(ValueError):
            index_details([record("g", "hybrid_page", True, 1)] * 2, {"g"})

    def test_missing_or_invalid_metric_cannot_shrink_gold_denominator(self):
        data = [q("g", "answerable", "bound")]
        for field in ("fact_coverage", "all_facts", "fact_mrr"):
            for value in (None, float("nan"), float("inf"), -0.1, 1.1):
                with self.subTest(field=field, value=value):
                    rows = [record("g", "hybrid_page", True, 1),
                            record("g", "hybrid_table_page", True, 1)]
                    rows[0][field] = value
                    with self.assertRaises(ValueError):
                        analyze(data, rows)

    def test_frozen_input_hashes_must_match_experiment(self):
        summary = {"split": "eval", "tier": "explicit", "methods": {
            "hybrid_page": {}, "hybrid_table_page": {}},
            "dataset_sha256": "gold-v1", "facts_sha256": "table-v1"}
        validate_summary(summary, "explicit", "gold-v1", "table-v1")
        for gold, facts in (("changed", "table-v1"), ("gold-v1", "changed")):
            with self.subTest(gold=gold, facts=facts), self.assertRaises(ValueError):
                validate_summary(summary, "explicit", gold, facts)
        del summary["facts_sha256"]
        with self.assertRaises(ValueError):
            validate_summary(summary, "explicit", "gold-v1", "table-v1")

    def test_tiers_include_unscorable_legacy_and_separate_silver(self):
        data = [q("e", "answerable", "bound"), q("s", "answerable", "bound", "silver"),
                q("l", "answerable", "no_source_anchor", "legacy"),
                q("n", "negative", "not_applicable")]
        rows = [record(item["id"], method, item["binding_status"] == "bound",
                       (1 if item["id"] == "e" else 0) if item["binding_status"] == "bound" else None)
                for method in ("hybrid_page", "hybrid_table_page") for item in data]
        out = analyze(data, rows, "all")
        tiers = out["comparison"]["by_tier"]
        self.assertEqual(tiers["explicit"]["counts"], {"gold": 1, "negative": 1})
        self.assertEqual(tiers["explicit"]["baseline_fact_coverage"], 1)
        self.assertEqual(tiers["silver"]["baseline_fact_coverage"], 0)
        self.assertIsNone(tiers["legacy"]["baseline_fact_coverage"])
        self.assertEqual(tiers["legacy"]["counts"], {"unbound": 1})
        self.assertEqual(len(out["comparison"]["pairs"]), 2)
        self.assertIn("legacy | 1 | 0 | 0 | 1 | N/A", to_markdown(out))

    def test_no_gold_returns_na_not_perfect_or_zero_score(self):
        data = [q("n", "negative", "not_applicable"), q("u", "answerable", "no_source_anchor")]
        rows = [record(item["id"], method, False)
                for item in data for method in ("hybrid_page", "hybrid_table_page")]
        out = analyze(data, rows)
        self.assertIsNone(out["methods"]["hybrid_page"]["fact_coverage"])
        self.assertIsNone(out["comparison"]["fact_coverage_delta_pp"])
        self.assertIn("N/A", to_markdown(out))

    def test_nonfinite_latency_is_rejected(self):
        data = [q("n", "negative", "not_applicable")]
        rows = [record("n", method, False) for method in ("hybrid_page", "hybrid_table_page")]
        rows[0]["total_ms"] = float("nan")
        with self.assertRaises(ValueError):
            analyze(data, rows)


if __name__ == "__main__":
    unittest.main()
