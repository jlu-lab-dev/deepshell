"""验证应用检索入口可切换 RRF；使用模拟候选，不连接正式知识库。"""

import ctypes
import sys
from unittest.mock import Mock

import pytest

if sys.platform == "win32":
    ctypes.WinDLL(r"C:\Windows\System32\MSVCP140.dll")

from rag.rag_manager import RAGManager


def make_rag(strategy="rrf", enabled=True):
    rag = object.__new__(RAGManager.__wrapped__)
    rag.config = {"hybrid_search": {
        "enabled": enabled, "fusion_strategy": strategy, "rrf_k": 60,
        "keyword_top_k": 4, "semantic_top_k": 3,
    }}
    rag.self_rag_flag = False
    rag._bm25_search = Mock(return_value=[{
        "chroma_id": "a", "content": "证据", "metadata": {"knowledge_base": "server"},
        "bm25_score": 99,
    }])
    rag.base_search = Mock(return_value=[{
        "chroma_id": "a", "content": "证据", "metadata": {"knowledge_base": "server"},
        "score": 0.2,
    }])
    rag.hybrid_search = Mock(return_value=[{"chroma_id": "legacy"}])
    rag._optimize_results = Mock(return_value=[{"chroma_id": "verified"}])
    return rag


def test_app_rrf_uses_same_candidates_and_preserves_sources():
    rag = make_rag()
    result = rag.search("问题", k=3, knowledge_bases=["server"])
    assert result[0]["chroma_id"] == "a"
    assert result[0]["rrf_score"] == pytest.approx(2 / 61)
    assert result[0]["metadata"]["knowledge_base"] == "server"
    assert result[0]["semantic_distance"] == 0.2
    rag._bm25_search.assert_called_once_with("问题", top_k=4, knowledge_bases=["server"])
    rag.base_search.assert_called_once_with("问题", k=3, knowledge_bases=["server"])
    rag.hybrid_search.assert_not_called()


def test_app_legacy_remains_default():
    rag = make_rag("legacy")
    del rag.config["hybrid_search"]["fusion_strategy"]
    assert rag.search("问题", k=3, knowledge_bases=["server"]) == [{"chroma_id": "legacy"}]
    rag.hybrid_search.assert_called_once_with("问题", k=6, knowledge_bases=["server"])
    rag._bm25_search.assert_not_called()


@pytest.mark.parametrize("kb_ids,k", [([], 3), (["server"], 0), (["server"], -1)])
def test_app_rrf_empty_selection_or_nonpositive_k(kb_ids, k):
    rag = make_rag()
    assert rag.search("问题", k=k, knowledge_bases=kb_ids) == []
    rag._bm25_search.assert_not_called()
    rag.base_search.assert_not_called()


def test_app_rrf_respects_self_rag_and_disabled_hybrid():
    rag = make_rag()
    rag.self_rag_flag = True
    assert rag.search("问题", k=2) == [{"chroma_id": "verified"}]
    rag._bm25_search.assert_called_once_with("问题", top_k=4, knowledge_bases=["default"])
    assert rag._optimize_results.call_args.args[2] == 2
    rag = make_rag(enabled=False)
    assert rag.search("问题", k=2)[0]["bm25_score"] == 0
    rag.base_search.assert_called_once_with("问题", k=2, knowledge_bases=None)
    rag._bm25_search.assert_not_called()
