"""模块：RAG Cross-Encoder 精排。

文件职责：
- 将 BM25 与 Dense 的独立候选先合并去重，再由 BGE Cross-Encoder 重排；
- 基于真实 Chroma ID 去重，并对知识库来源做强校验；
- 不改 Chroma 索引，不调用生成模型；延迟加载模型，单元测试可注入评分器。
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Any, Callable, Sequence

DEFAULT_MODEL = "BAAI/bge-reranker-base"


def merge_candidates(
    bm25: Sequence[dict[str, Any]],
    dense: Sequence[dict[str, Any]],
    allowed_kbs: Sequence[str],
) -> list[dict[str, Any]]:
    """先合并两路候选而不做最终 Top-K 截断，避免融合阶段提前丢弃有效证据。"""
    allowed = {str(kb) for kb in allowed_kbs}
    if not allowed:
        return []
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for channel, rows in (("bm25", bm25), ("dense", dense)):
        for item in rows:
            meta = item.get("metadata") or {}
            kb_id = str(meta.get("knowledge_base", ""))
            if kb_id not in allowed:
                raise ValueError(f"粗检索返回不允许的知识库：{kb_id}")
            cid = str(item.get("chroma_id") or meta.get("chunk_id") or "")
            if not cid:
                raise ValueError("粗检索结果没有真实 Chroma ID")
            if cid in seen:
                continue
            if not str(item.get("content") or "").strip():
                continue
            seen.add(cid)
            obj = dict(item)
            obj["chroma_id"] = cid
            obj.setdefault("retrieval_channel", channel)
            merged.append(obj)
    return merged


def rerank_candidates(
    query: str,
    candidates: Sequence[dict[str, Any]],
    scorer: Callable[[list[tuple[str, str]]], Sequence[float]],
    *,
    top_k: int,
    allowed_kbs: Sequence[str],
) -> list[dict[str, Any]]:
    """纯函数精排，支持 Mock Scorer，零模型依赖单测。"""
    if top_k <= 0:
        raise ValueError("top_k 必须大于 0")
    # 双重隔离和 Chroma ID 去重。单列表复用合并逻辑即可。
    unique = merge_candidates(candidates, [], allowed_kbs)
    if not unique:
        return []
    scores = list(scorer([(query, str(item["content"])) for item in unique]))
    if len(scores) != len(unique):
        raise ValueError("Cross-Encoder 返回分数数量与候选数量不一致")
    ranked: list[dict[str, Any]] = []
    for item, value in zip(unique, scores):
        score = float(value)
        if not math.isfinite(score):
            raise ValueError("Cross-Encoder 返回 NaN/Inf 分数")
        obj = dict(item)
        obj["retrieval_score"] = item.get("score", item.get("bm25_score"))
        obj["rerank_score"] = score
        obj["score"] = score
        ranked.append(obj)
    # 相同分数时以 Chroma ID 做确定性排序，便于复现实验。
    return sorted(ranked, key=lambda x: (-x["rerank_score"], x["chroma_id"]))[:top_k]


@lru_cache(maxsize=2)
def get_cross_encoder(model_name: str, device: str, max_length: int):
    """延迟加载且进程内缓存模型；下载仅在首次真实精排时发生。"""
    from sentence_transformers import CrossEncoder
    return CrossEncoder(model_name, device=device, max_length=max_length)


def rerank_with_bge(
    query: str,
    candidates: Sequence[dict[str, Any]],
    *,
    top_k: int,
    allowed_kbs: Sequence[str],
    model_name: str = DEFAULT_MODEL,
    device: str = "cpu",
    batch_size: int = 8,
    max_length: int = 512,
) -> list[dict[str, Any]]:
    """加载 BGE Reranker，对输入的全部候选一次批量精排。"""
    if batch_size <= 0 or max_length <= 0:
        raise ValueError("batch_size、max_length 必须大于 0")
    if not candidates:
        return []
    model = get_cross_encoder(model_name, device, max_length)
    return rerank_candidates(
        query, candidates,
        lambda pairs: model.predict(pairs, batch_size=batch_size, show_progress_bar=False),
        top_k=top_k, allowed_kbs=allowed_kbs,
    )
