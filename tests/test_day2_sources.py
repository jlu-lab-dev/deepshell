"""隔离的检索与引用回归测试；不加载用户模型配置或正式知识库。"""

import ctypes
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

if sys.platform == "win32":
    ctypes.WinDLL(r"C:\Windows\System32\MSVCP140.dll")

from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import AIMessageChunk

from chat import assistant as assistant_module
from chat import chat_task
from chat.message_helpers import (
    build_llm_context, get_message_parts, iter_history_messages_with_sources,
    make_text_message,
)
from chat.model_manager import ModelManager
from chat.rag_citations import make_citation_docs, make_citation_prompt
from rag.rag_manager import RAGManager
from ui.chat import bubble_message


def bare_rag():
    rag = object.__new__(RAGManager.__wrapped__)
    rag.config = {"hybrid_search": {"score_threshold": -100}}
    rag.self_rag_flag = False
    return rag


def record(cid, kb="server", content="系统安装要求", page=6):
    return {
        "chroma_id": cid, "content": content, "score": 0.2,
        "metadata": {"knowledge_base": kb, "doc_id": f"doc-{cid}",
                     "source": f"/manuals/{cid}.pdf", "page": page},
    }


def test_bm25_filters_before_top_k_and_breaks_ties_by_id():
    rag = bare_rag()
    rag._bm25_index = Mock()
    rag._bm25_index.get_scores.return_value = [100, -1, -1, 5]
    rag._bm25_chroma_ids = ["desktop", "z-server", "a-server", "missing"]
    rag._bm25_content_map = {
        "desktop": {"text": "desktop", "metadata": {"knowledge_base": "desktop"}},
        "z-server": {"text": "server", "metadata": {"knowledge_base": "server"}},
        "a-server": {"text": "server", "metadata": {"knowledge_base": "server"}},
        "missing": {"text": "unknown", "metadata": None},
    }
    results = rag._bm25_search("安装", top_k=1, knowledge_bases=["server"])
    assert [r["chroma_id"] for r in results] == ["a-server"]
    assert results[0]["bm25_score"] == -1
    assert rag._bm25_search("安装", knowledge_bases=[]) == []
    assert rag._bm25_search("安装", top_k=0, knowledge_bases=["server"]) == []


def test_bm25_none_selects_only_default():
    rag = bare_rag()
    rag._bm25_index = Mock()
    rag._bm25_index.get_scores.return_value = [1, 100]
    rag._bm25_chroma_ids = ["default-doc", "server-doc"]
    rag._bm25_content_map = {
        cid: {"text": cid, "metadata": {"knowledge_base": kb}}
        for cid, kb in [("default-doc", "default"), ("server-doc", "server")]
    }
    assert [r["chroma_id"] for r in rag._bm25_search("安装")] == ["default-doc"]


def test_hybrid_keeps_equal_text_from_different_records():
    rag = bare_rag()
    a, b = record("a"), record("b")
    rag._bm25_search = Mock(return_value=[{**a, "bm25_score": 1}, {**b, "bm25_score": 2}])
    rag._semantic_search = Mock(return_value=[b, a])
    results = rag.hybrid_search("安装", knowledge_bases=["server"])
    assert {r["chroma_id"] for r in results} == {"a", "b"}
    assert len({r["content"] for r in results}) == 1
    assert {r["metadata"]["doc_id"] for r in results} == {"doc-a", "doc-b"}
    assert results[0]["score"] == pytest.approx(0.3 * 2 + 0.7 * 0.2)
    rag._bm25_search.assert_called_once_with("安装", top_k=20, knowledge_bases=["server"])
    rag._semantic_search.assert_called_once_with("安装", k=20, knowledge_bases=["server"])


def test_semantic_reads_legacy_ids_and_filters_chroma_results():
    rag = bare_rag()
    collection = Mock()
    rag.vector_db = SimpleNamespace(_collection=collection)
    rag.embedding = Mock()
    rag.embedding.embed_query.return_value = [1.0, 0.0]
    collection.get.side_effect = lambda where, include: {
        "ids": ["legacy-server-a", "legacy-server-b"]
        if where["knowledge_base"]["$in"] == ["server"] else []
    }
    collection.query.return_value = {
        "ids": [["legacy-server-a", "legacy-server-b", "desktop"]],
        "documents": [["相同原文"] * 3],
        "metadatas": [[{"knowledge_base": kb, "source": source} for kb, source in [
            ("server", "a.pdf"), ("server", "b.pdf"), ("desktop", "desktop.pdf")
        ]]],
        "distances": [[0.0, 0.1, 0.0]],
    }
    for search in (rag.base_search, rag._semantic_search):
        results = search("安装", k=20, knowledge_bases=["server"])
        assert {r["chroma_id"] for r in results} == {"legacy-server-a", "legacy-server-b"}
        assert all("chunk_id" not in r["metadata"] for r in results)
        assert results[0]["distance"] <= results[1]["distance"]
    collection.query.assert_called_with(
        query_embeddings=[[1.0, 0.0]], n_results=2,
        where={"knowledge_base": {"$in": ["server"]}},
        include=["documents", "metadatas", "distances"]
    )
    assert rag._semantic_search("安装", knowledge_bases=[]) == []
    assert rag._semantic_search("安装", knowledge_bases=["missing"]) == []
    assert rag._semantic_search("安装", k=0) == []
    assert rag._semantic_search("安装") == []


@pytest.mark.skipif(
    os.environ.get("DEEPSHELL_TEST_NATIVE_CHROMA") != "1",
    reason="原生 HNSW 检查需显式启用；在子进程运行以隔离访问冲突"
)
def test_native_chroma_legacy_ids():
    result = subprocess.run(
        [sys.executable, "-c", "import runpy; runpy.run_path("
         "'tests/test_day2_sources.py')['_native_legacy_chroma_check']()"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30
    )
    assert result.returncode == 0, (
        f"独立内存 Chroma 检查失败，子进程退出码 {result.returncode}\n"
        f"{result.stdout[-1000:]}\n{result.stderr[-2000:]}"
    )


def _native_legacy_chroma_check():
    import chromadb
    from chromadb.config import Settings

    client = chromadb.EphemeralClient(Settings(anonymized_telemetry=False))
    collection = client.create_collection(f"sources-test-{uuid.uuid4().hex}")
    try:
        collection.add(
            ids=["legacy-server-a", "legacy-server-b", "legacy-desktop"],
            documents=["系统安装要求"] * 3,
            metadatas=[
                {"knowledge_base": "server", "source": "a.pdf", "page": 6},
                {"knowledge_base": "server", "source": "b.pdf", "page": 7},
                {"knowledge_base": "desktop", "source": "desktop.pdf", "page": 0},
            ],
            embeddings=[[1.0, 0.0], [0.8, 0.2], [1.0, 0.0]],
        )
        rag = bare_rag()
        rag.vector_db = SimpleNamespace(_collection=collection)
        rag.embedding = Mock()
        rag.embedding.embed_query.return_value = [1.0, 0.0]
        for search in (rag.base_search, rag._semantic_search):
            results = search("安装", k=20, knowledge_bases=["server"])
            assert {r["chroma_id"] for r in results} == {"legacy-server-a", "legacy-server-b"}
            assert all(r["metadata"]["knowledge_base"] == "server" for r in results)
            assert all("chunk_id" not in r["metadata"] for r in results)
            assert results[0]["distance"] <= results[1]["distance"]
        assert rag._semantic_search("安装", knowledge_bases=[]) == []
        assert rag._semantic_search("安装", knowledge_bases=["missing"]) == []
        assert rag._semantic_search("安装", k=0) == []
        assert rag._semantic_search("安装") == []
    finally:
        client.delete_collection(collection.name)


@pytest.mark.parametrize("raw,expected", [(0, 1), (6, 7), (None, None), ("invalid", None), (-1, None)])
def test_citations_preserve_identity_and_convert_page(raw, expected):
    citation = make_citation_docs([record("legacy", page=raw)], {"server": "服务器 V4"})[0]
    assert citation["page"] == expected
    assert citation["metadata"]["page"] == raw
    assert citation["chroma_id"] == citation["chunk_id"] == "legacy"
    assert citation["doc_id"] == "doc-legacy"
    assert citation["knowledge_base_name"] == "服务器 V4"


def test_prompt_and_restored_history_share_numbering_and_support_old_docs():
    docs = make_citation_docs([record("a"), record("b")])
    evidence = make_citation_prompt(docs)
    assert "[1] 文件：a.pdf" in evidence and "[2] 文件：b.pdf" in evidence
    assert "PDF 第 7 页" in evidence
    assert evidence in build_llm_context("安装要求？", relevant_docs=docs)
    assert "页码未知" in make_citation_prompt([{"source": "old.pdf", "content": "旧证据"}])
    assert "[1] 文件：old.pdf" in build_llm_context(
        "旧问题", relevant_docs=[{"source": "old.pdf", "content": "旧证据"}]
    )


@pytest.mark.parametrize("has_results", [True, False])
def test_assistant_uses_numbered_evidence_without_internal_json(monkeypatch, has_results):
    assistant = object.__new__(assistant_module.Assistant)
    assistant.session_id, assistant.model, assistant.prompt_template = "session", "model", "prompt"
    assistant.kb_list = ["server"]
    assistant.model_manager = Mock()
    assistant.rag_manager = Mock()
    assistant.rag_manager.search.return_value = [record("a")] if has_results else []
    repo = Mock()
    repo.list_knowledge_bases.return_value = [SimpleNamespace(id="server", name="服务器 V4")]
    monkeypatch.setattr(assistant_module, "KnowledgeBaseRepository", lambda: repo)
    original = ["如何安装？"]
    assistant.chat_stream(original)
    assert original == ["如何安装？"]
    prompt = assistant.model_manager.chat_stream.call_args.kwargs["messages"][-1]
    assert "__RAG_DOCS_JSON__" not in prompt
    assert ("[1] 文件：a.pdf" in prompt) is has_results
    assert ("没有返回相关证据" in prompt) is not has_results
    assistant.model_manager.set_pending_rag_turn.assert_called_once_with(
        "session", "如何安装？", assistant.last_rag_docs
    )


def test_non_rag_turn_resets_sources():
    assistant = object.__new__(assistant_module.Assistant)
    assistant.session_id, assistant.model, assistant.prompt_template = "session", "model", "prompt"
    assistant.kb_list, assistant.last_rag_docs = [], [record("stale")]
    assistant.rag_manager, assistant.model_manager = Mock(), Mock()
    assistant.chat_stream(["你好"])
    assert assistant.last_rag_docs == []
    assistant.rag_manager.search.assert_not_called()
    assistant.model_manager.set_pending_rag_turn.assert_called_once_with("session", "你好", [])


def bare_model_manager():
    manager = object.__new__(ModelManager.__wrapped__)
    manager.memory, manager._pending_rag_turn = {}, {}
    manager.conversation_repo = Mock()
    manager.conversation_repo.get_messages.return_value = []
    return manager


def test_history_saves_original_question_and_sources_only_on_latest_user():
    manager = bare_model_manager()
    history = InMemoryChatMessageHistory()
    history.add_user_message("较早问题")
    history.add_ai_message("较早回答")
    history.add_user_message("本轮问题及额外证据")
    history.add_message(AIMessageChunk(content="回答 [1]"))
    manager.memory["session"] = history
    docs = make_citation_docs([record("a")])
    manager.set_pending_rag_turn("session", "原始问题", docs)
    manager._persist_stream_messages("session")
    calls = manager.conversation_repo.add_message.call_args_list
    older = get_message_parts(calls[0].args[2])
    latest = get_message_parts(calls[2].args[2])
    assert older["user_input"] == "较早问题" and older["relevant_docs"] == []
    assert latest["user_input"] == "原始问题" and latest["relevant_docs"] == docs
    assert "[1] 文件：a.pdf" in latest["content"]
    assert "session" not in manager._pending_rag_turn


def test_history_accepts_legacy_json_marker():
    manager = bare_model_manager()
    history = InMemoryChatMessageHistory()
    docs = [{"source": "old.pdf", "content": "旧证据"}]
    history.add_user_message("旧问题\n__RAG_DOCS_JSON__:" + json.dumps(docs))
    history.add_ai_message("旧回答")
    manager.memory["session"] = history
    manager._persist_stream_messages("session")
    saved = get_message_parts(manager.conversation_repo.add_message.call_args_list[0].args[2])
    assert saved["user_input"] == "旧问题" and saved["relevant_docs"] == docs


def test_reopened_history_pairs_sources_without_leaking_to_later_turns():
    docs = make_citation_docs([record("a")])
    messages = [
        SimpleNamespace(role="user", content=make_text_message("user", user_input="问题", relevant_docs=docs)),
        SimpleNamespace(role="assistant", content=make_text_message("assistant", user_input="回答 [1]")),
        SimpleNamespace(role="user", content=make_text_message("user", user_input="无检索问题")),
        SimpleNamespace(role="assistant", content=make_text_message("assistant", user_input="普通回答")),
        SimpleNamespace(role="assistant", content="早期纯文本历史"),
    ]
    restored = list(iter_history_messages_with_sources(messages))
    assert [sources for _, _, sources in restored] == [[], docs, [], [], []]
    # 老式 source/content 来源也保留，未知页码不能补成虚构的第 1 页。
    legacy = [{"source": "old.pdf", "content": "旧证据"}]
    messages[0].content = make_text_message("user", user_input="旧问题", relevant_docs=legacy)
    assert list(iter_history_messages_with_sources(messages))[1][2] == legacy


@pytest.mark.parametrize("fail", [False, True])
def test_pending_sources_are_cleared_after_stream_end_or_error(fail):
    manager = bare_model_manager()
    manager.conversation_repo = None
    manager.set_pending_rag_turn("session", "问题", [record("a")])

    def stream(*args):
        yield SimpleNamespace(content="回答")
        if fail:
            raise RuntimeError("model failed")

    manager._get_chat_stream = stream
    result = manager.chat_stream("model", ["问题"], session_id="session")
    if fail:
        with pytest.raises(RuntimeError):
            list(result)
    else:
        assert list(result) == ["回答"]
    assert not manager._pending_rag_turn


def test_chat_task_sends_sources_before_response(qtbot, monkeypatch):
    docs = make_citation_docs([record("a")])
    assistant = Mock(last_rag_docs=docs)
    assistant.chat_stream.return_value = (chunk for chunk in ["回答", " [1]"])
    monkeypatch.setattr(chat_task, "Assistant", lambda _: assistant)
    task = chat_task.ChatTask()
    events = []
    task.sources_signal.connect(lambda value: events.append(("sources", value)))
    task.update_signal.connect(lambda value: events.append(("text", value)))
    task.run()
    assert events[:3] == [("sources", []), ("sources", docs), ("text", "回答")]
    assert events[-1] == ("text", "回答 [1]")


def test_source_panel_expands_escapes_html_and_clears(qtbot, monkeypatch):
    monkeypatch.setattr(bubble_message, "ConfigManager", lambda: SimpleNamespace(
        app_config={"logo": "ui/icon/DeepShell/shell.png"}
    ))
    bubble = bubble_message.BubbleMessage("回答 [1]", "", bubble_message.MessageType.TEXT, 12)
    qtbot.addWidget(bubble)
    assert bubble.source_toggle.isHidden()
    docs = make_citation_docs([record("a", content="<img src='x'> & 原文\n第二行")])
    docs[0]["filename"] = "<b>手册</b>.pdf"
    bubble.set_sources(docs)
    assert not bubble.source_toggle.isHidden()
    assert bubble.source_detail.isHidden()
    bubble.source_toggle.setChecked(True)
    assert not bubble.source_detail.isHidden()
    text = bubble.source_detail.text()
    assert "&lt;img" in text and "&lt;b&gt;手册" in text and "&amp;" in text
    assert "PDF 第 7 页" in text and "分块 ID：a" in text
    bubble.set_sources([])
    assert bubble.source_toggle.isHidden() and bubble.source_detail.isHidden()
    assert not bubble.source_detail.text()
