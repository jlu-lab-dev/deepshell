"""文件：rag/table_retrieval.py

模块：企业知识库 RAG / 结构化表格检索旁路。
职责：从人工核验的 PDF 表格事实中选择与查询匹配的行，再定位已有 Chroma Chunk。
设计约束：只读 Chroma、只返回真实 Chunk UUID、不修改向量索引和知识库隔离。
重要：本模块中的表格事实不是引用，引用必须来自 Chroma 的原始文档片段。
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable

FACTS_PATH = Path(__file__).resolve().parents[1] / "evals/benchmark_v1/data/table_facts.jsonl"


def normalized(value: object) -> str:
    """统一中文兼容字符、大小写和 PDF 中多余的空白。"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value or ""))).casefold()


def basename(value: object) -> str:
    return str(value or "").replace("\\", "/").rsplit("/", 1)[-1]


def load_facts(path: Path = FACTS_PATH) -> list[dict[str, Any]]:
    """读取静态结构化事实；首次不联网，也不加载 Embedding。"""
    if not path.is_file():
        raise FileNotFoundError(f"没有表格事实库：{path}")
    facts = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    required = {"id", "knowledge_base", "kind", "label", "value", "source", "page"}
    if any(required - row.keys() for row in facts):
        raise ValueError("table_facts.jsonl 缺少必填字段")
    if len({row["id"] for row in facts}) != len(facts):
        raise ValueError("表格事实 ID 重复")
    return facts


def _requested_levels(query: str) -> set[str]:
    """只在问题明确涉及运行级别时解析数字，避免误把 OS 版本号当作级别。"""
    query = unicodedata.normalize("NFKC", query)
    if not re.search(r"运行级别|runlevel", query, flags=re.IGNORECASE):
        return set()
    cleaned = re.sub(r"[Vv]\s*\d+(?:\.\d+)*", "", query)
    cleaned = re.sub(r"第\s*\d+\.\d+\s*节", "", cleaned)
    cleaned = re.sub(r"表\s*\d+[-－]\d+", "", cleaned)
    # 对“运行级别 2 和 5”或“运行级别 3～6”提取多个值。
    start = re.search(r"运行级别|runlevel", cleaned, flags=re.IGNORECASE)
    suffix = cleaned[start.end():] if start else ""
    levels = set()
    for range_match in re.finditer(r"(?<![\d.])([0-6])\s*[~～至到-]\s*([0-6])(?![\d.])", suffix[:80]):
        lo, hi = map(int, range_match.groups())
        if lo <= hi:
            levels.update(str(i) for i in range(lo, hi + 1))
    # 后续数字一般是级别枚举；这里只取问题前 80 字，防止长引文误触发。
    return levels | set(re.findall(r"(?<![\d.])[0-6](?![\d.])", suffix[:80]))


def select_rows(query: str, allowed_names: Iterable[str], facts: list[dict]) -> list[dict]:
    """根据明确的表格意图选择记录，不能仅因同一 KB 就把全表加入上下文。"""
    allowed = set(allowed_names)
    q = normalized(query)
    shortcut_intent = bool(re.search(r"快捷键|组合键|热键|按键|什么键|键位", q))
    wanted_levels = _requested_levels(query)
    matched: list[tuple[int, dict]] = []
    for row in facts:
        if row["knowledge_base"] not in allowed:
            continue
        label = normalized(row["label"])
        if row["kind"] == "shortcut":
            if not shortcut_intent:
                continue
            # 比较长的具体功能名称优先，例如“在同一应用程序中反向切换”。
            if label in q:
                matched.append((len(label) + 10, row))
        elif row["kind"] == "runlevel" and row["label"] in wanted_levels:
            matched.append((100, row))
    matched.sort(key=lambda item: (-item[0], item[1]["id"]))
    result = []
    for _, row in matched:
        if row["kind"] == "shortcut":
            label = normalized(row["label"])
            # 只排除长标签内部的短标签，保留另一个明确提问的功能及运行级别事实。
            covering = [(m.start(), m.end()) for _, other in matched
                        if other["kind"] == "shortcut" and len(normalized(other["label"])) > len(label)
                        for m in re.finditer(re.escape(normalized(other["label"])), q)]
            occurrences = list(re.finditer(re.escape(label), q))
            if occurrences and all(any(start <= m.start() and m.end() <= end for start, end in covering)
                                   for m in occurrences):
                continue
        result.append(row)
    return result


def _same_source_page(meta: dict, row: dict, kb_id: str) -> bool:
    if str(meta.get("knowledge_base", "")) != str(kb_id):
        return False
    try:
        page_ok = int(meta.get("page", -1)) == int(row["page"]) - 1
    except (ValueError, TypeError):
        return False
    return page_ok and basename(meta.get("source")) == basename(row["source"])


def _context_strength(text: str, row: dict) -> int:
    """只认可原始分块中真实出现的对应关系，不拼造替代证据。"""
    content = normalized(text)
    label, value = normalized(row["label"]), normalized(row["value"])
    if row["kind"] == "shortcut":
        # 要求功能与按键的原文对应关系，避免将相邻行的值错配。
        return 2 if label + value in content else 0
    # 运行级别要求数字与完整定义相邻，不能只命中其他行中的定义前缀。
    return 2 if re.search(r"(?<!\d)" + re.escape(label + value), content) else 0


def retrieve_table_chunks(collection: Any, rows: list[dict], name_to_id: dict[str, str],
                          max_chunks: int = 3) -> list[dict[str, Any]]:
    """将匹配的结构化行映射回真实 Chroma Chunk；任何错误不静默跨库兜底。"""
    if max_chunks < 1 or not rows:
        return []
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    page_cache: dict[tuple[str, int], dict] = {}
    for row in rows:
        kb_id = name_to_id.get(row["knowledge_base"])
        if not kb_id:
            continue
        page_zero = int(row["page"]) - 1
        cache_key = (kb_id, page_zero)
        if cache_key not in page_cache:
            page_cache[cache_key] = collection.get(
                where={"$and": [
                    {"knowledge_base": {"$eq": str(kb_id)}},
                    {"page": {"$eq": page_zero}},
                ]},
                include=["documents", "metadatas"],
            )
        result = page_cache[cache_key]
        found = []
        for cid, content, meta in zip(result.get("ids") or [],
                                      result.get("documents") or [],
                                      result.get("metadatas") or []):
            if not _same_source_page(meta or {}, row, kb_id):
                continue
            strength = _context_strength(content or "", row)
            if strength:
                found.append((strength, str(cid), content, meta))
        # 同一行只返回最合适的真实 Chunk，避免把页面上的全部碎片塞进 Top-3。
        found.sort(key=lambda x: (-x[0], x[1]))
        for _, cid, content, meta in found[:1]:
            if cid in seen:
                continue
            seen.add(cid)
            hits.append({"chroma_id": cid, "content": content, "metadata": meta,
                         "table_hit": True, "table_fact_id": row["id"]})
            if len(hits) >= max_chunks:
                return hits
    return hits


def merge_results(table_hits: list[dict], base_hits: list[dict], k: int = 3) -> list[dict]:
    """表格命中排在前面，其余保留原始 Hybrid 顺序；以真实 Chroma ID 去重。"""
    if k <= 0:
        raise ValueError("k 必须大于 0")
    result, seen = [], set()
    for item in [*table_hits, *base_hits]:
        cid = str(item.get("chroma_id") or (item.get("metadata") or {}).get("chunk_id") or "")
        if not cid:
            raise ValueError("候选缺少真实 Chroma ID，拒绝用于可靠评测")
        if cid in seen:
            continue
        seen.add(cid)
        result.append(item)
        if len(result) >= k:
            break
    return result


def table_hybrid_search(rag: Any, query: str, allowed_ids: list[str],
                        name_to_id: dict[str, str], facts: list[dict], k: int = 3) -> list[dict]:
    """显式的组合策略：Hybrid 粗检索 + 表格精确路由（非神经 Reranker）。"""
    base_hits = rag.hybrid_search(query, k=k, knowledge_bases=allowed_ids)
    allowed = set(map(str, allowed_ids))
    if any(str((item.get("metadata") or {}).get("knowledge_base", "")) not in allowed for item in base_hits):
        raise RuntimeError("Hybrid 返回跨知识库结果")
    allowed_names = {name for name, cid in name_to_id.items() if str(cid) in allowed}
    rows = select_rows(query, allowed_names, facts)
    extra = retrieve_table_chunks(rag.vector_db._collection, rows, name_to_id, max_chunks=k)
    merged = merge_results(extra, base_hits, k)
    # 防御性再次检查来源；如果原 Hybrid 意外跨库，不应让它进入后续 Prompt。
    for item in merged:
        if str((item.get("metadata") or {}).get("knowledge_base", "")) not in allowed:
            raise RuntimeError("表格旁路发现跨知识库结果")
    return merged
