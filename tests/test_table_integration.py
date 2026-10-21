"""应用表格检索、聊天与 Agent 来源链路；不加载模型或访问正式索引。"""

import ctypes
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

if sys.platform == "win32":
    ctypes.WinDLL(r"C:\Windows\System32\MSVCP140.dll")

from chat import assistant as assistant_module
from database.repository import knowledge_base_repository
from rag.rag_manager import RAGManager
from rag import table_retrieval


def chunk(cid, text, page=34, kb="desktop"):
    return {"chroma_id": cid, "content": text, "metadata": {
        "knowledge_base": kb, "source": "zm_yhsc.pdf", "doc_id": "manual", "page": page,
    }}


@pytest.fixture
def app_rag(monkeypatch):
    rag = object.__new__(RAGManager.__wrapped__)
    rag.config = {
        "hybrid_search": {"enabled": True, "fusion_strategy": "hybrid_table"},
        "page_context": {"enabled": True, "max_pages": 1, "max_added_chunks": 12, "max_total_chars": 2500},
    }
    rag.self_rag_flag = False
    table = chunk("table", "移动窗口 Alt+F7")
    sibling = chunk("sibling", "同页原文：其他操作说明")
    noise = [chunk(f"noise-{i}", "无关片段", page=77) for i in range(3)]
    rag.hybrid_search = Mock(return_value=noise)
    rag._bm25_search = Mock()
    rag.base_search = Mock()
    data = [table, sibling, *noise]
    collection = Mock()

    def get(where, include):
        filters = {key: value["$eq"] for clause in where["$and"] for key, value in clause.items()}
        selected = [r for r in data if all(r["metadata"].get(k) == v for k, v in filters.items())]
        return {"ids": [r["chroma_id"] for r in selected],
                "documents": [r["content"] for r in selected],
                "metadatas": [r["metadata"] for r in selected]}

    collection.get.side_effect = get
    rag.vector_db = SimpleNamespace(_collection=collection)
    repo = SimpleNamespace(list_knowledge_bases=lambda: [
        SimpleNamespace(name="KB_A_Desktop_V5", id="desktop"),
        SimpleNamespace(name="KB_B_Server_V4", id="server"),
    ])
    monkeypatch.setattr(knowledge_base_repository, "KnowledgeBaseRepository", lambda: repo)
    monkeypatch.setattr(assistant_module, "KnowledgeBaseRepository", lambda: repo)
    return rag


def test_app_uses_table_then_exact_top_three(app_rag, monkeypatch):
    load = Mock(wraps=table_retrieval.load_facts)
    monkeypatch.setattr(table_retrieval, "load_facts", load)
    for _ in range(2):
        hits = app_rag.search("移动窗口的快捷键是什么？", k=3, knowledge_bases=["desktop"])
        assert [r["chroma_id"] for r in hits] == ["table", "noise-0", "noise-1"]
    load.assert_called_once_with()
    app_rag.hybrid_search.assert_called_with("移动窗口的快捷键是什么？", k=3, knowledge_bases=["desktop"])
    app_rag._bm25_search.assert_not_called()
    app_rag.base_search.assert_not_called()


def test_missing_table_asset_falls_back_to_hybrid(app_rag, monkeypatch):
    monkeypatch.setattr(table_retrieval, "load_facts", Mock(side_effect=FileNotFoundError("missing")))
    hits = app_rag.search("移动窗口快捷键", k=3, knowledge_bases=["desktop"])
    assert [r["chroma_id"] for r in hits] == ["noise-0", "noise-1", "noise-2"]
    app_rag.hybrid_search.assert_called_once_with("移动窗口快捷键", k=3, knowledge_bases=["desktop"])


def test_empty_selection_does_not_load_table_or_search(app_rag, monkeypatch):
    load = Mock()
    monkeypatch.setattr(table_retrieval, "load_facts", load)
    assert app_rag.search("移动窗口快捷键", knowledge_bases=[]) == []
    assert app_rag.search("移动窗口快捷键", k=0, knowledge_bases=["desktop"]) == []
    load.assert_not_called()
    app_rag.hybrid_search.assert_not_called()


def test_table_lookup_respects_selected_kb(app_rag):
    app_rag.hybrid_search.return_value = [chunk("server-result", "服务器原文", kb="server")]
    hits = app_rag.search("移动窗口快捷键", knowledge_bases=["server"])
    assert [r["chroma_id"] for r in hits] == ["server-result"]
    app_rag.vector_db._collection.get.assert_not_called()


@pytest.mark.parametrize("entry", ["chat", "chat_stream", "build_rag_enriched_message"])
def test_all_assistant_entries_share_table_page_and_citations(app_rag, entry):
    assistant = object.__new__(assistant_module.Assistant)
    assistant.rag_manager = app_rag
    assistant.kb_list = ["desktop"]
    assistant.session_id, assistant.model, assistant.prompt_template = "session", "model", "prompt"
    assistant.model_manager = Mock()
    question = "移动窗口的快捷键是什么？"
    original = [question]
    if entry == "build_rag_enriched_message":
        prompt, docs = assistant.build_rag_enriched_message(question)
        assistant.model_manager.chat.assert_not_called()
        assistant.model_manager.chat_stream.assert_not_called()
    else:
        getattr(assistant, entry)(original)
        prompt = getattr(assistant.model_manager, entry).call_args.kwargs["messages"][-1]
        docs = assistant.last_rag_docs
    assert original == [question]
    assert [d["chroma_id"] for d in docs] == ["table", "noise-0", "noise-1", "sibling"]
    assert "移动窗口 Alt+F7" in prompt and "同页原文：其他操作说明" in prompt
    assert "[1] 文件：zm_yhsc.pdf" in prompt and "[4] 文件：zm_yhsc.pdf" in prompt
    assert docs[0]["page"] == 35 and docs[0]["knowledge_base"] == "desktop"
    assert "__RAG_DOCS_JSON__" not in prompt
    if entry == "chat_stream":
        assistant.model_manager.set_pending_rag_turn.assert_called_once_with("session", question, docs)


def test_agent_without_selected_kb_does_not_retrieve(app_rag):
    assistant = object.__new__(assistant_module.Assistant)
    assistant.kb_list, assistant.rag_manager = [], app_rag
    assert assistant.build_rag_enriched_message("你好") == ("你好", [])
    app_rag.hybrid_search.assert_not_called()


@pytest.mark.parametrize("entry", ["chat", "chat_stream"])
def test_failed_retrieval_clears_previous_sources(entry):
    assistant = object.__new__(assistant_module.Assistant)
    assistant.last_rag_docs = [{"source": "stale.pdf"}]
    assistant._retrieve_rag_docs = Mock(side_effect=RuntimeError("retrieval failed"))
    assistant.model_manager = Mock()
    with pytest.raises(RuntimeError, match="retrieval failed"):
        getattr(assistant, entry)(["问题"])
    assert assistant.last_rag_docs == []
    assistant.model_manager.chat.assert_not_called()
    assistant.model_manager.chat_stream.assert_not_called()
