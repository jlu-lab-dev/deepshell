"""同页扩展与聊天接入回归；不连接正式 Chroma 或模型。"""

import copy
import ctypes
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

if sys.platform == "win32":
    ctypes.WinDLL(r"C:\Windows\System32\MSVCP140.dll")

from chat import assistant as assistant_module
from rag.page_context import expand_pdf_page_context


def chunk(cid, kb="server", doc="manual", page=6, text="证据", index=None, source="server.pdf"):
    metadata = {"knowledge_base": kb, "page": page, "source": source}
    if doc is not None:
        metadata["doc_id"] = doc
    if index is not None:
        metadata["chunk_index"] = index
    return {"chroma_id": cid, "content": text, "metadata": metadata}


class Collection:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def get(self, where, include):
        self.calls.append((where, include))
        rows = [row for row in self.rows if all(
            row["metadata"].get(key) == condition["$eq"]
            for clause in where["$and"] for key, condition in clause.items()
        )]
        return {
            "ids": [row["chroma_id"] for row in rows],
            "documents": [row["content"] for row in rows],
            "metadatas": [row["metadata"] for row in rows],
        }


def expand(rows, seeds, **kwargs):
    collection = Collection(rows)
    results = expand_pdf_page_context(
        SimpleNamespace(_collection=collection), seeds,
        knowledge_bases=["server"], **kwargs
    )
    return results, collection


def test_expansion_keeps_same_kb_document_page_and_real_ids():
    seed = chunk("level2", text="级别 2：多用户", index=0)
    missing = chunk("level5", text="级别 5：图形界面", index=1)
    rows = [
        missing, seed, chunk("other-kb", kb="desktop"),
        chunk("other-doc", doc="another"), chunk("other-page", page=7),
    ]
    original = copy.deepcopy([seed, seed])
    result, collection = expand(rows, original)
    assert [r["chroma_id"] for r in result] == ["level2", "level5"]
    assert original == [seed, seed]
    assert collection.calls == [({"$and": [
        {"knowledge_base": {"$eq": "server"}},
        {"doc_id": {"$eq": "manual"}},
        {"page": {"$eq": 6}},
    ]}, ["documents", "metadatas"])]


def test_legacy_source_fallback_uses_full_path():
    seed = chunk("seed", doc=None, source="/a/manual.pdf")
    result, collection = expand([
        seed, chunk("same-page", doc=None, source="/a/manual.pdf"),
        chunk("same-basename", doc=None, source="/b/manual.pdf"),
    ], [seed])
    assert [r["chroma_id"] for r in result] == ["seed", "same-page"]
    assert collection.calls[0][0]["$and"][1] == {"source": {"$eq": "/a/manual.pdf"}}


def test_page_budget_counts_unique_original_pages():
    seeds = [chunk(f"seed-{i}", page=i) for i in range(4)]
    seeds.insert(1, chunk("same-page", page=0))
    rows = [chunk(f"extra-{i}", page=i) for i in range(4)]
    result, collection = expand(rows, seeds, max_pages=3)
    assert len(collection.calls) == 3
    assert [r["chroma_id"] for r in result[len(seeds):]] == ["extra-0", "extra-1", "extra-2"]


def test_chunk_budget_and_chunk_order():
    seed = chunk("seed", index=0)
    rows = [chunk(f"extra-{i}", index=i) for i in [3, 1, 2]]
    result, _ = expand(rows, [seed], max_added_chunks=2)
    assert [r["chroma_id"] for r in result] == ["seed", "extra-1", "extra-2"]


def test_character_budget_limits_only_added_full_chunks():
    seed = chunk("seed", text="原始证据" * 20)
    rows = [chunk("large", text="超出新增预算", index=1),
            chunk("small", text="完整证据", index=2), chunk("last", text="余", index=3)]
    result, _ = expand(rows, [seed], max_total_chars=4)
    assert [r["chroma_id"] for r in result] == ["seed", "small"]
    assert result[0]["content"] == seed["content"]
    assert result[1]["content"] == "完整证据"


@pytest.mark.parametrize("limits", [{"max_pages": 0}, {"max_added_chunks": 0}, {"max_total_chars": 0}])
def test_zero_budget_returns_filtered_originals_without_queries(limits):
    seed = chunk("seed")
    result, collection = expand([], [seed, seed, chunk("foreign", kb="desktop")], **limits)
    assert result == [seed]
    assert not collection.calls


@pytest.mark.parametrize("page", [None, -1, "invalid", 6.5, float("inf"), True])
def test_invalid_page_is_not_queried(page):
    seed = chunk("seed", page=page)
    result, collection = expand([], [seed])
    assert result == [seed] and not collection.calls


def test_missing_identity_and_empty_selection_are_not_queried():
    seed = chunk("seed", doc=None, source="")
    result, collection = expand([], [seed])
    assert result == [seed] and not collection.calls
    vector_db = SimpleNamespace(_collection=Mock())
    assert expand_pdf_page_context(vector_db, [chunk("a")], []) == []
    assert expand_pdf_page_context(vector_db, []) == []
    vector_db._collection.get.assert_not_called()


def test_returned_metadata_is_verified_even_if_collection_ignores_filters():
    seed = chunk("seed")
    rows = [chunk("kb", kb="desktop"), chunk("doc", doc="other"), chunk("page", page=7)]
    collection = Mock()
    collection.get.return_value = {
        "ids": [row["chroma_id"] for row in rows],
        "documents": [row["content"] for row in rows],
        "metadatas": [row["metadata"] for row in rows],
    }
    assert expand_pdf_page_context(
        SimpleNamespace(_collection=collection), [seed], ["server"]
    ) == [seed]


def test_query_failure_preserves_evidence_and_logs(caplog):
    seed = chunk("seed")
    collection = Mock()
    collection.get.side_effect = RuntimeError("read failed")
    assert expand_pdf_page_context(
        SimpleNamespace(_collection=collection), [seed], ["server"]
    ) == [seed]
    assert any(record.exc_info for record in caplog.records)


@pytest.mark.parametrize("enabled", [True, False])
def test_chat_expands_before_citations_prompt_and_pending_history(monkeypatch, enabled):
    assistant = object.__new__(assistant_module.Assistant)
    assistant.session_id, assistant.model, assistant.prompt_template = "session", "Qwen", "prompt"
    assistant.kb_list = ["server"]
    assistant.model_manager = Mock()
    seed = chunk("level2", text="级别 2：多用户")
    target_id = "17bc4e81-55eb-470d-8b4d-e3d0b7ee6229"
    sibling = chunk(target_id, text="级别 5：图形界面")
    collection = Collection([seed, sibling])
    assistant.rag_manager = SimpleNamespace(
        config={"page_context": {"enabled": enabled}}, search=Mock(return_value=[seed]),
        vector_db=SimpleNamespace(_collection=collection)
    )
    repo = Mock()
    repo.list_knowledge_bases.return_value = [SimpleNamespace(id="server", name="服务器 V4")]
    monkeypatch.setattr(assistant_module, "KnowledgeBaseRepository", lambda: repo)
    assistant.chat_stream(["运行级别 2 和 5 有何区别？"])
    docs = assistant.last_rag_docs
    assert len(docs) == (2 if enabled else 1)
    assert all(doc["page"] == 7 for doc in docs)
    prompt = assistant.model_manager.chat_stream.call_args.kwargs["messages"][-1]
    assert ("级别 5：图形界面" in prompt) is enabled
    assert ("[2] 文件：server.pdf" in prompt) is enabled
    assert len(collection.calls) == int(enabled)
    if enabled:
        assert docs[1]["chroma_id"] == target_id
    assistant.model_manager.set_pending_rag_turn.assert_called_once_with(
        "session", "运行级别 2 和 5 有何区别？", docs
    )
