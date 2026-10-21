"""文件：test_table_retrieval.py
职责：不依赖真实 Chroma/模型，测试表格路由、知识库隔离、来源验证及 Gold 复用。
"""
import pytest

from rag.table_retrieval import (normalized, load_facts, select_rows,
                                 retrieve_table_chunks, merge_results, table_hybrid_search)
from evals.benchmark_v1.table_experiment import summarize

FACTS = load_facts()


def test_fact_count():
    assert len(FACTS) == 30
    assert len({r["id"] for r in FACTS}) == 30


def test_table_shortcut_exact():
    rows = select_rows("移动窗口的快捷键是什么？", {"KB_A_Desktop_V5"}, FACTS)
    assert [(r["label"], r["value"]) for r in rows] == [("移动窗口", "Alt+F7")]


def test_longest_label_prevents_ambiguity():
    rows = select_rows("在同一应用程序中反向切换的默认快捷键", {"KB_A_Desktop_V5"}, FACTS)
    assert len(rows) == 1
    assert rows[0]["value"] == "Shift+Super+`"


def test_missing_intent_no_table_injection():
    assert select_rows("如何在方德系统新建账户？", {"KB_A_Desktop_V5"}, FACTS) == []


def test_runlevels_ignore_version():
    rows = select_rows("V4.0 用户手册运行级别 2 和 5 分别是什么？",
                       {"KB_B_Server_V4"}, FACTS)
    assert {r["label"] for r in rows} == {"2", "5"}
    assert select_rows("V4.0 运行级别 3～6 的含义", {"KB_B_Server_V4"}, FACTS)


def test_cross_kb_isolation():
    assert select_rows("启动终端快捷键", {"KB_B_Server_V4"}, FACTS) == []
    assert select_rows("运行级别5是什么", {"KB_A_Desktop_V5"}, FACTS) == []


class FakeCollection:
    def __init__(self, data):
        self.data = data
    def get(self, where, include):
        clauses = where["$and"]
        filters = {k: v["$eq"] for x in clauses for k, v in x.items()}
        rows = [r for r in self.data if all(r["meta"].get(k) == v for k, v in filters.items())]
        return {"ids": [r["id"] for r in rows],
                "documents": [r["text"] for r in rows],
                "metadatas": [r["meta"] for r in rows]}


def test_real_chunk_only_and_wrong_source_rejected():
    kb_id = "kb-a"
    rows = select_rows("启动终端的快捷键", {"KB_A_Desktop_V5"}, FACTS)
    assert rows
    data = [
        {"id": "good", "text": "启动终端 Ctrl+Alt+T", "meta": {"knowledge_base": kb_id, "source": "zm_yhsc.pdf", "page": 34}},
        {"id": "wrong-kb", "text": "启动终端 Ctrl+Alt+T", "meta": {"knowledge_base": "kb-b", "source": "zm_yhsc.pdf", "page": 34}},
        {"id": "wrong-file", "text": "启动终端 Ctrl+Alt+T", "meta": {"knowledge_base": kb_id, "source": "else.pdf", "page": 34}},
    ]
    result = retrieve_table_chunks(FakeCollection(data), rows, {"KB_A_Desktop_V5": kb_id})
    assert len(result) == 1
    assert result[0]["chroma_id"] == "good"
    assert result[0]["metadata"]["source"] == "zm_yhsc.pdf"


def test_fail_closed_when_chunk_has_only_value():
    rows = select_rows("启动终端快捷键", {"KB_A_Desktop_V5"}, FACTS)
    data = [{"id": "bad", "text": "快捷键 Ctrl+Alt+T", "meta": {"knowledge_base": "kb-a", "source": "zm_yhsc.pdf", "page": 34}}]
    assert retrieve_table_chunks(FakeCollection(data), rows, {"KB_A_Desktop_V5": "kb-a"}) == []


def test_merge_and_dedup():
    mk = lambda cid: {"chroma_id": cid, "content": cid, "metadata": {"knowledge_base": "kb"}}
    got = merge_results([mk("a"), mk("b")], [mk("b"), mk("c"), mk("d")], k=3)
    assert [r["chroma_id"] for r in got] == ["a", "b", "c"]


def test_empty_table_fallback():
    class Rag:
        def hybrid_search(self, query, k, knowledge_bases):
            return [{"chroma_id": "existing", "content": "x", "metadata": {"knowledge_base": "kb-a"}}]
        class Vec:
            _collection = FakeCollection([])
        vector_db = Vec()
    result = table_hybrid_search(Rag(), "新建用户账户", ["kb-a"], {"KB_A_Desktop_V5": "kb-a"}, FACTS, k=3)
    assert result[0]["chroma_id"] == "existing"


def test_summary_denominators():
    records = [
        {"method": "hybrid", "eligible": True, "category": "shortcut", "fact_coverage": 0.5,
         "base_fact_coverage": 0.5, "all_facts": False, "fact_mrr": 0.5, "kb_leak": 0,
         "retrieval_ms": 10, "total_ms": 12, "context_chunks": 2, "context_chars": 100},
        {"method": "hybrid", "eligible": False, "category": "cross_kb", "fact_coverage": None,
         "base_fact_coverage": None, "all_facts": None, "fact_mrr": None, "kb_leak": 0,
         "retrieval_ms": 10, "total_ms": 12, "context_chunks": 0, "context_chars": 0}
    ]
    stats = summarize(records)["hybrid"]
    assert stats["gold_questions"] == 1
    assert stats["negative_questions"] == 1
    assert stats["fact_coverage"] == 0.5
    records[0]["task_type"] = "answerable"
    records[1]["task_type"] = "negative"
    records.append({**records[1], "task_type": "answerable", "category": "faq"})
    stats = summarize(records)["hybrid"]
    assert stats["negative_questions"] == 1
    assert stats["unbound_answerable_questions"] == 1
    assert stats["gold_questions"] == 1


def test_multi_shortcuts_keep_distinct_labels():
    rows = select_rows("移动窗口和最小化窗口分别用什么快捷键？", {"KB_A_Desktop_V5"}, FACTS)
    assert {r["label"] for r in rows} == {"移动窗口", "最小化窗口"}


def test_mixed_table_facts_preserved():
    rows = select_rows("启动终端的快捷键和运行级别5分别是什么？",
                       {"KB_A_Desktop_V5", "KB_B_Server_V4"}, FACTS)
    assert {(r["kind"], r["label"]) for r in rows} == {("shortcut", "启动终端"), ("runlevel", "5")}


def test_runlevel_suffix_versions_ranges_and_decimals():
    allowed = {"KB_B_Server_V4"}
    assert {r["label"] for r in select_rows("运行级别5是什么（方德V4.0）？", allowed, FACTS)} == {"5"}
    assert {r["label"] for r in select_rows("运行级别1和3～6的含义", allowed, FACTS)} == {"1", "3", "4", "5", "6"}
    assert select_rows("运行级别3.5是什么", allowed, FACTS) == []


def test_shortcut_value_on_another_row_rejected():
    rows = select_rows("移动窗口快捷键", {"KB_A_Desktop_V5"}, FACTS)
    data = [{"id": "mismatched", "text": "移动窗口 Alt+F8\n改变窗口大小 Alt+F7",
             "meta": {"knowledge_base": "a", "source": "zm_yhsc.pdf", "page": 34}}]
    assert retrieve_table_chunks(FakeCollection(data), rows, {"KB_A_Desktop_V5": "a"}) == []


def test_runlevel_number_and_full_definition_required():
    row = next(r for r in FACTS if r["id"] == "server-runlevel-3")
    meta = {"knowledge_base": "b", "source": row["source"], "page": 6}
    data = [{"id": "wrong-number", "text": "13 完全多用户模式。", "meta": meta},
            {"id": "prefix-only", "text": "3 完全多用户模式的其他说明。", "meta": meta}]
    assert retrieve_table_chunks(FakeCollection(data), [row], {"KB_B_Server_V4": "b"}) == []


def test_raw_hybrid_leak_is_not_hidden_by_table_priority():
    class Rag:
        def hybrid_search(self, query, k, knowledge_bases):
            return [{"chroma_id": "leak", "content": "x", "metadata": {"knowledge_base": "b"}}]
    with pytest.raises(RuntimeError, match="跨知识库"):
        table_hybrid_search(Rag(), "移动窗口快捷键", ["a"], {"KB_A_Desktop_V5": "a"}, FACTS)


def test_nonpositive_top_k_rejected():
    with pytest.raises(ValueError, match="k"):
        merge_results([], [], k=0)


def test_multiple_runlevel_chunks_support_and_groups():
    from evals.benchmark_v1.candidate_diagnostics import score_groups

    rows = select_rows("运行级别1和4分别是什么？", {"KB_B_Server_V4"}, FACTS)
    data = [{"id": r["id"], "text": r["label"] + " " + r["value"],
             "meta": {"knowledge_base": "b", "source": r["source"], "page": 6}} for r in rows]
    hits = retrieve_table_chunks(FakeCollection(data), rows, {"KB_B_Server_V4": "b"})
    ids = [h["chroma_id"] for h in hits]
    groups = [{"chunk_ids": [r["id"]]} for r in rows]
    assert len(ids) == 2
    assert score_groups(groups, ids, 1)["fact_coverage"] == 0.5
    assert score_groups(groups, ids, 3)["all_facts"] is True
