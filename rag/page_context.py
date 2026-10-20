"""检索后的同页上下文扩展：只读现有 Chroma 记录，不重新计算向量。"""

import logging
from typing import Any, Dict, List, Optional


def _page_index(value):
    """只接受非负整页索引，缺失或无效页码不参与扩展。"""
    if isinstance(value, bool):
        return None
    try:
        page = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if page < 0 or (isinstance(value, float) and value != page):
        return None
    return page


def expand_pdf_page_context(
    vector_db: Any,
    results: List[Dict[str, Any]],
    knowledge_bases: Optional[List[str]] = None,
    max_pages: int = 3,
    max_added_chunks: int = 24,
    max_total_chars: int = 6000,
) -> List[Dict[str, Any]]:
    """保留检索顺序，追加同页原文，按真实 Chroma ID 去重。

    max_total_chars 仅限制新增原文字符数，不截断已有证据或单个分块。
    优先用 doc_id 隔离文档，旧索引缺失 doc_id 时用完整 source 回退。
    仅原始命中页可触发扩展，新增分块不触发下一轮扩展。
    """
    allowed = {str(kb) for kb in (
        knowledge_bases if knowledge_bases is not None else ["default"]
    )}
    expanded = []
    existing_ids = set()
    for result in results:
        metadata = result.get("metadata") or {}
        if str(metadata.get("knowledge_base", "")) not in allowed:
            continue
        cid = result.get("chroma_id")
        if cid is not None:
            cid = str(cid)
            if cid in existing_ids:
                continue
            existing_ids.add(cid)
        expanded.append(result)

    if not expanded or max_pages <= 0 or max_added_chunks <= 0 or max_total_chars <= 0:
        return expanded

    visited_pages = set()
    added_chunks = 0
    added_chars = 0
    for result in list(expanded):
        if (len(visited_pages) >= max_pages or added_chunks >= max_added_chunks
                or added_chars >= max_total_chars):
            break
        metadata = result.get("metadata") or {}
        kb_id = str(metadata.get("knowledge_base", ""))
        doc_id = str(metadata.get("doc_id") or "")
        source = str(metadata.get("source") or "")
        page = _page_index(metadata.get("page"))
        if page is None:
            continue
        if doc_id:
            identity_key, identity_value = "doc_id", doc_id
        elif source:
            identity_key, identity_value = "source", source
        else:
            continue

        page_key = (kb_id, identity_key, identity_value, page)
        if page_key in visited_pages:
            continue
        visited_pages.add(page_key)
        where_filter = {
            "$and": [
                {"knowledge_base": {"$eq": kb_id}},
                {identity_key: {"$eq": identity_value}},
                {"page": {"$eq": page}},
            ]
        }
        try:
            records = vector_db._collection.get(
                where=where_filter, include=["documents", "metadatas"]
            )
        except Exception:
            logging.exception(
                "[RAG] 同页扩展失败，保留原始检索证据: kb=%s, %s=%s, page=%s",
                kb_id, identity_key, identity_value, page
            )
            continue

        rows = list(zip(
            records.get("ids") or [], records.get("documents") or [],
            records.get("metadatas") or []
        ))
        # 新索引按 chunk_index 阅读；旧索引没有该字段时保留数据库返回顺序。
        rows.sort(key=lambda row: (
            _page_index((row[2] or {}).get("chunk_index")) is None,
            _page_index((row[2] or {}).get("chunk_index")) or 0,
        ))
        for cid, text, meta in rows:
            if added_chunks >= max_added_chunks or added_chars >= max_total_chars:
                break
            meta = meta or {}
            # 再核对返回值，确保错误或不完整的元数据也不会造成跨库、跨页混入。
            if (str(meta.get("knowledge_base", "")) != kb_id
                    or str(meta.get(identity_key) or "") != identity_value
                    or _page_index(meta.get("page")) != page):
                continue
            if cid is None or not str(cid) or str(cid) in existing_ids:
                continue
            if not isinstance(text, str) or not text.strip():
                continue
            if added_chars + len(text) > max_total_chars:
                continue
            expanded.append({
                "chroma_id": str(cid), "content": text, "metadata": dict(meta)
            })
            existing_ids.add(str(cid))
            added_chunks += 1
            added_chars += len(text)

    return expanded
