"""检索指标单元测试；不读取真实 PDF、数据库或 API。"""
from evals.retrieval.retrieval_eval import score_question, aggregate


def test_page_hit_is_not_strict_recall():
    q = {
        "knowledge_bases": ["KB_B_Server_V4"], "task_type": "answerable",
        "evidence": [{"source": "server.pdf", "page": 7}], "gold_chunk_ids": None,
    }
    r = [{"chunk_id": "id-1", "source": "server.pdf", "page": 7,
          "knowledge_base_name": "KB_B_Server_V4"}]
    x = score_question(q, r, 3)
    assert x["evidence_page_hit"] is True
    assert "strict_chunk_recall" not in x


def test_strict_mrr_and_recall():
    q = {
        "knowledge_bases": ["A"], "task_type": "answerable", "evidence": [],
        "gold_chunk_ids": ["a", "b"]
    }
    r = [{"chunk_id": x, "source": "x", "page": 1, "knowledge_base_name": "A"}
         for x in ["x", "b", "y"]]
    x = score_question(q, r, 3)
    assert x["strict_chunk_recall"] == 0.5
    assert x["strict_mrr"] == 0.5


def test_negative_checks_scope_not_refusal():
    q = {"knowledge_bases": ["A"], "task_type": "cross_kb_unanswerable"}
    r = [{"chunk_id": "z", "knowledge_base_name": "B", "source": "b.pdf", "page": 1}]
    assert score_question(q, r, 3)["kb_leak"] is True
    assert "evidence_page_hit" not in score_question(q, r, 3)


def test_aggregate_skips_unannotated_chunk_metric():
    q = {"knowledge_bases": ["A"], "task_type": "answerable",
         "evidence": [{"source": "x", "page": 1}], "gold_chunk_ids": None}
    records = [{"method": "dense", "task_type": "answerable", "latency_ms": 30,
                "question": q, "results": [{"source": "x", "page": 1,
                "chunk_id": "id", "knowledge_base_name": "A"}]}]
    r = aggregate(records, [1])[0]
    assert r["evidence_page_hit"] == 1.0
    assert r["strict_chunk_recall"] is None
