"""测试企业基准 Top-K 粗召回诊断的 AND/OR 指标和错误分类，不需要模型或 Chroma。"""
from evals.benchmark_v1.candidate_diagnostics import score_groups, select_cases, summarize


def test_and_or_groups():
    groups = [
        {"chunk_ids": ["A", "A_alt"]},
        {"chunk_ids": ["B"]},
    ]
    ranked = ["noise", "A_alt", "noise2", "B"]
    at3 = score_groups(groups, ranked, 3)
    assert at3["fact_coverage"] == 0.5
    assert at3["all_facts"] is False
    assert at3["fact_ranks"] == [2, None]
    assert score_groups(groups, ranked, 5)["all_facts"] is True


def test_mrr_and_alternatives():
    score = score_groups([{"chunk_ids": ["x", "y"]}], ["y", "x"], 3)
    assert score["fact_mrr"] == 1.0
    assert score["fact_ranks"] == [1]


def test_top3_miss_top20_hit():
    gold = [{"chunk_ids": ["answer"]}]
    ranked = ["A", "B", "C", "answer"]
    row = {
        "method": "hybrid", "id": "Q01", "category": "shortcut",
        "question": "test", "eligible": True, "fact_count": 1,
        "metrics": {"3": score_groups(gold, ranked, 3),
                    "20": score_groups(gold, ranked, 20)},
    }
    good, missing = select_cases([row], [3, 20])
    assert len(good) == 1 and not missing
    # 即使额外请求 K=1，诊断仍必须以 Top-3 为比较基准。
    top3_hit = {**row, "metrics": {
        "1": score_groups(gold, ["A", "answer"], 1),
        "3": score_groups(gold, ["A", "answer"], 3),
        "20": score_groups(gold, ["A", "answer"], 20),
    }}
    good, missing = select_cases([top3_hit], [1, 3, 20])
    assert not good and not missing


def test_top20_missing():
    gold = [{"chunk_ids": ["answer"]}]
    ranked = ["A", "B", "C"]
    row = {
        "method": "hybrid", "id": "Q02", "category": "shortcut",
        "question": "test", "eligible": True, "fact_count": 1,
        "metrics": {"3": score_groups(gold, ranked, 3),
                    "20": score_groups(gold, ranked, 20)},
    }
    good, missing = select_cases([row], [3, 20])
    assert not good and len(missing) == 1


def test_denominators_and_negatives():
    gold = [{"chunk_ids": ["answer"]}]
    rec = {
        "method": "hybrid", "id": "Q1", "category": "faq", "task_type": "answerable",
        "eligible": True, "kb_leak": False, "latency_ms": 50,
        "returned_chunks": 2,
        "metrics": {"3": score_groups(gold, ["answer"], 3),
                    "20": score_groups(gold, ["answer"], 20)},
    }
    neg = {**rec, "id": "Q2", "task_type": "negative", "eligible": False,
           "kb_leak": True, "metrics": {}}
    s = summarize([rec, neg], [3, 20])["hybrid"]
    assert s["questions"] == 2
    assert s["gold_questions"] == 1
    assert s["negative_questions"] == 1
    assert s["kb_leak_queries"] == 1
    assert s["by_k"]["3"]["fact_coverage"] == 1.0
