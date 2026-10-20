"""RAG 检索融合模块（Day 3）。

职责：按照 Chroma 记录 ID 合并 BM25、Dense 候选，使用 Reciprocal Rank Fusion
重排，不对不同分数尺度做直接加权；不连接数据库，也不调用 LLM。
"""

from __future__ import annotations

from typing import Any, Sequence


def rrf_fuse(
    rankings: Sequence[Sequence[dict[str, Any]]],
    top_k: int,
    rank_constant: int = 60,
) -> list[dict[str, Any]]:
    """融合若干已经按相关性排序的结果列表。

    参数：
        rankings: 多路检索结果，至少包含真实 chroma_id。
        top_k: 最终返回数量；非正数则返回空。
        rank_constant: RRF 平滑项，一般从 60 开始。

    返回值沿用 RAGManager 的 content / metadata / chroma_id / score 结构，
    score 是 RRF 分数（越大越相关）；semantic_distance 单独保留原始向量距离。
    同一列表内部的重复 ID 只计一次，避免重复累积分数。
    """
    if rank_constant < 0:
        raise ValueError("rank_constant 必须 >= 0")
    if top_k <= 0:
        return []

    merged: dict[str, dict[str, Any]] = {}
    for source_idx, items in enumerate(rankings):
        seen: set[str] = set()
        for original_rank, item in enumerate(items, start=1):
            cid = str(item.get("chroma_id") or "")
            if not cid:
                raise ValueError("RRF 候选缺少 chroma_id，不能按文本内容合并")
            if cid in seen:
                continue
            seen.add(cid)
            if cid not in merged:
                merged[cid] = {
                    "chroma_id": cid,
                    "content": item.get("content", ""),
                    "metadata": dict(item.get("metadata") or {}),
                    "score": 0.0,
                    "rrf_score": 0.0,
                    "bm25_score": None,
                    "semantic_distance": None,
                    "bm25_rank": None,
                    "dense_rank": None,
                }
            record = merged[cid]
            record["rrf_score"] += 1.0 / (rank_constant + original_rank)
            record["score"] = record["rrf_score"]
            if source_idx == 0:
                record["bm25_rank"] = original_rank
                if "bm25_score" in item:
                    record["bm25_score"] = item["bm25_score"]
            elif source_idx == 1:
                record["dense_rank"] = original_rank
                if "score" in item:
                    record["semantic_distance"] = item["score"]
            # 对所有来源都保留第一个可用 metadata；两种检索源的 ID 唯一对应同一 chunk。
            if not record["metadata"] and item.get("metadata"):
                record["metadata"] = dict(item["metadata"])

    return sorted(
        merged.values(),
        key=lambda record: (-record["rrf_score"], record["chroma_id"]),
    )[:top_k]
