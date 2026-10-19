"""将真实检索结果转换为统一引用，供聊天、历史记录和评测共用。"""

from pathlib import Path


def make_citation_docs(results, kb_names=None):
    """保留知识库、文档、Chroma ID、原文及 PDF 阅读器中的 1 起始页码。"""
    kb_names = kb_names or {}
    citations = []
    for number, result in enumerate(results, 1):
        metadata = result.get("metadata") or {}
        kb_id = str(metadata.get("knowledge_base", ""))
        raw_page = metadata.get("page")
        try:
            page = int(raw_page) + 1 if raw_page is not None else None
            if page is not None and page < 1:
                page = None
        except (TypeError, ValueError, OverflowError):
            page = None
        source = str(metadata.get("source") or "")
        chroma_id = result.get("chroma_id")
        citations.append({
            "number": number,
            "source": source,
            "filename": Path(source.replace("\\", "/")).name if source else "未知文件",
            "knowledge_base": kb_id,
            "knowledge_base_name": kb_names.get(kb_id, kb_id or "未知知识库"),
            "doc_id": metadata.get("doc_id"),
            "chroma_id": chroma_id,
            "chunk_id": metadata.get("chunk_id") or chroma_id,
            "chunk_index": metadata.get("chunk_index"),
            "page": page,
            "content": result.get("content") or "",
            "metadata": dict(metadata),
            "score": result.get("score"),
            "bm25_score": result.get("bm25_score"),
            "semantic_score": result.get("semantic_score"),
            "distance": result.get("distance"),
        })
    return citations


def make_citation_prompt(docs):
    """为本轮和历史上下文使用同一套证据编号；兼容旧 source/content 记录。"""
    parts = []
    for number, doc in enumerate(docs, 1):
        source = doc.get("source") or ""
        filename = doc.get("filename") or (
            Path(str(source).replace("\\", "/")).name if source else "未知文件"
        )
        kb = doc.get("knowledge_base_name") or doc.get("knowledge_base") or "未知知识库"
        page = doc.get("page")
        location = f"PDF 第 {page} 页" if page is not None else "页码未知"
        parts.append(
            f"[{number}] 文件：{filename}；知识库：{kb}；{location}\n"
            f"{doc.get('content') or ''}"
        )
    return "\n\n".join(parts)
