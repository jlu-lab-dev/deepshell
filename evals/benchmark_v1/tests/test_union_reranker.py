"""模块：精排及联合评测回归测试。
不下载模型，不连接 Chroma，使用假分数验证候选去重、隔离、精排与 Gold 计分。
"""
import pytest

from rag.cross_encoder_reranker import merge_candidates, rerank_candidates
from evals.benchmark_v1.rerank_experiment import percentile, prepare_evidence, score_or_none, summarize


def item(cid, text, kb="A"):
    return {"chroma_id": cid, "content": text, "metadata": {"knowledge_base": kb, "page": 6}}


def test_union_avoids_pre_truncation_and_dedups():
    a = [item("1", "wrong"), item("2", "right")]
    b = [item("1", "duplicate"), item("3", "correct")]
    merged = merge_candidates(a, b, ["A"])
    assert [c["chroma_id"] for c in merged] == ["1", "2", "3"]


def test_bge_scoring_reorders_correct_chunk():
    merged = merge_candidates([item("x", "wrong")], [item("y", "good")], ["A"])
    ranked = rerank_candidates("question", merged, lambda pairs: [0.2, 4.2], top_k=1, allowed_kbs=["A"])
    assert [r["chroma_id"] for r in ranked] == ["y"]
    assert ranked[0]["rerank_score"] == 4.2


def test_kb_boundary_is_enforced():
    with pytest.raises(ValueError, match="不允许"):
        merge_candidates([item("id1", "secret", "B")], [], ["A"])


def test_invalid_scorer_length_rejected():
    with pytest.raises(ValueError, match="数量"):
        rerank_candidates("q", [item("id", "x")], lambda _: [], top_k=1, allowed_kbs=["A"])


def test_gold_two_facts_and_alternatives():
    q = {
        "id": "multi", "task_type": "answerable", "binding_status": "bound",
        "gold_evidence_groups": [{"chunk_ids": ["a", "b"]}, {"chunk_ids": ["c"]}],
    }
    assert score_or_none(q, [item("b", "x")])["fact_coverage"] == 0.5
    assert score_or_none(q, [item("b", "x"), item("c", "y")])["all_facts"] is True


def test_negative_not_counted_as_gold():
    q = {"task_type": "negative", "binding_status": "not_applicable"}
    assert score_or_none(q, []) is None


def test_percentile_nearest_rank():
    assert percentile([1, 3, 4, 9], 0.95) == 9


def test_summary_handles_negative():
    rows = [{"method": "bm25", "category": "cross_kb", "task_type": "negative",
             "metrics": None, "total_ms": 1, "context_chunks": 0, "context_chars": 0,
             "retrieval_ms": 1, "rerank_ms": 0, "expand_ms": 0, "candidate_pool_size": 0}]
    result = summarize(rows)["bm25"]
    assert result["fact_coverage"]["n"] == 0
    assert result["negative_questions"] == 1


def test_empty_duplicate_keeps_valid_text_and_channel():
    merged = merge_candidates([item("x", " ")], [item("x", "valid")], ["A"])
    ranked = rerank_candidates("q", merged, lambda _: [1.0], top_k=1, allowed_kbs=["A"])
    assert len(ranked) == 1
    assert ranked[0]["content"] == "valid"
    assert ranked[0]["retrieval_channel"] == "dense"


@pytest.mark.parametrize("score", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_scores_rejected(score):
    with pytest.raises(ValueError, match="NaN/Inf"):
        rerank_candidates("q", [item("x", "text")], lambda _: [score], top_k=1, allowed_kbs=["A"])


def test_prepare_scores_union_before_final_k(monkeypatch):
    from evals.benchmark_v1 import rerank_experiment

    calls = []
    def search(rag, method, query, k, kbs):
        calls.append((method, k, kbs))
        return [item(f"{method}-{i}", "answer" if i == 19 else "noise") for i in range(k)]

    def rerank(query, candidates, *, top_k, allowed_kbs, **kwargs):
        assert len(candidates) == 40
        return rerank_candidates(query, candidates,
                                 lambda pairs: [float(text == "answer") for _, text in pairs],
                                 top_k=top_k, allowed_kbs=allowed_kbs)

    monkeypatch.setattr(rerank_experiment, "rerank_with_bge", rerank)
    original, final, pool, *_ = prepare_evidence(
        object(), "union_rerank", "q", ["A"], final_k=3, candidate_k=20,
        model="fake", device="cpu", batch_size=8, max_pages=1, max_added=12,
        max_chars=2500, search_one=search,
    )
    assert calls == [("bm25", 20, ["A"]), ("dense", 20, ["A"])]
    assert pool == 40 and len(final) == 3
    assert {r["chroma_id"] for r in original[:2]} == {"bm25-19", "dense-19"}


def test_summary_separates_top_k_from_expanded_context():
    q = {"id": "multi", "task_type": "answerable", "binding_status": "bound",
         "gold_evidence_groups": [{"chunk_ids": ["a"]}, {"chunk_ids": ["b"]}]}
    rows = [{"method": "union_rerank_page", "category": "faq", "task_type": "answerable",
             "base_metrics": score_or_none(q, [item("a", "a")]),
             "metrics": score_or_none(q, [item("a", "a"), item("b", "b")]),
             "total_ms": 10, "context_chunks": 2, "context_chars": 2,
             "retrieval_ms": 1, "rerank_ms": 8, "expand_ms": 1, "candidate_pool_size": 40}]
    result = summarize(rows)["union_rerank_page"]
    assert result["base_fact_coverage"] == {"value": 0.5, "n": 1}
    assert result["base_all_facts"] == {"value": 0.0, "n": 1}
    assert result["fact_coverage"] == {"value": 1.0, "n": 1}
    assert result["all_facts"] == {"value": 1.0, "n": 1}
