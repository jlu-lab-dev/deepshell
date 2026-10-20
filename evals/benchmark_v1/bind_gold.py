"""为 Enterprise Benchmark v1 将 PDF 原文锚点绑定到当前 Chroma 的真实 Chunk ID。

用途：只读索引；不同导入产生不同 UUID，所以不在发布版数据中写死自动生成的 ID。
职责：验证 KB/文档/页码/原文四个字段；每条事实可对应多个等价分块 (OR)，
不同事实组成多个 group (AND)。无法绑定的题不会被伪装成召回失败。
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import re
from collections import Counter
from pathlib import Path
from typing import Any


def normalize(s: Any) -> str:
    """PDF 换行/空格与 PyPDFLoader 内容可能不同；仅统一空白和大小写。"""
    return re.sub(r"\s+", "", str(s or "")).casefold()


def filename(value: Any) -> str:
    return str(value or "").replace("\\", "/").rsplit("/", 1)[-1]


def bind_one(question: dict, hits: list[dict]) -> dict:
    """为单条问题绑定：hits 每项含 id/content/metadata；无副作用。"""
    output = dict(question)
    if output.get("task_type") != "answerable":
        output["binding_status"] = "not_applicable"
        return output

    # 旧版有手工 UUID；检查它们是否真的仍存在于当前知识库索引。
    if output.get("gold_evidence_groups"):
        known_ids = {str(h["id"]) for h in hits}
        if all(group.get("chunk_ids") and set(map(str, group["chunk_ids"])) <= known_ids
               for group in output["gold_evidence_groups"]):
            output["binding_status"] = "preexisting_ids_verified"
        else:
            output["binding_status"] = "preexisting_ids_invalid"
            output["gold_evidence_groups"] = []
        return output

    anchors = [e for e in output.get("evidence", []) if e.get("quote")]
    if not anchors:
        output["binding_status"] = "no_source_anchor"
        return output

    groups = []
    # 每个 entry 是必需事实（AND），同一事实的多个来源证据是 OR。
    for entry in anchors:
        matched = set()
        variants = [entry, *entry.get("alternatives", [])]
        for variant in variants:
            pg = int(variant["page"])
            src = filename(variant["source"])
            quote = normalize(variant["quote"])
            for h in hits:
                m = h.get("metadata") or {}
                try:
                    page = int(m.get("page", -999)) + 1
                except (ValueError, TypeError):
                    continue
                if page != pg or filename(m.get("source")) != src:
                    continue
                if quote in normalize(h.get("content")):
                    matched.add(str(h["id"]))
        groups.append({
            "fact": entry.get("fact") or "来源原文证据",
            "chunk_ids": sorted(matched),
            "source": filename(entry["source"]),
            "page": int(entry["page"]),
            "quote": entry["quote"],
        })

    if all(group["chunk_ids"] for group in groups):
        output["gold_evidence_groups"] = groups
        output["binding_status"] = "bound"
    else:
        # 不计算有缺失证据组的事实覆盖，否则会把标注缺失当成模型错误。
        output["gold_evidence_groups"] = []
        output["binding_status"] = "partial_or_missing"
        output["unmatched_evidence"] = [
            {k: group[k] for k in ("fact", "source", "page", "quote")}
            for group in groups if not group["chunk_ids"]
        ]
    return output


def bind_questions(records: list[dict], kb_to_hits: dict[str, list[dict]]) -> list[dict]:
    """按用户选择的知识库处理；保留原 split、题号和题型。"""
    result = []
    for q in records:
        if q.get("task_type") != "answerable":
            result.append(bind_one(q, []))
            continue
        kbs = q.get("knowledge_bases", [])
        if len(kbs) != 1:
            raise ValueError(f"{q['id']} 的知识库数量不是 1，需显式扩展绑定逻辑")
        result.append(bind_one(q, kb_to_hits.get(kbs[0], [])))
    return result


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def dump_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="按来源与 PDF 原文锚点绑定真实 Chroma UUID，不改动数据库")
    parser.add_argument("--dataset", type=Path, default=Path("evals/benchmark_v1/data/enterprise_all.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("evals/benchmark_v1/data/enterprise_bound.jsonl"))
    parser.add_argument("--report", type=Path, default=Path("evals/benchmark_v1/data/binding_report.json"))
    args = parser.parse_args()
    questions = read_jsonl(args.dataset)
    if platform.system() == "Windows":
        ctypes.WinDLL(r"C:\Windows\System32\MSVCP140.dll")
    from database.repository.knowledge_base_repository import KnowledgeBaseRepository
    import chromadb
    from config.config_manager import ConfigManager
    repo = KnowledgeBaseRepository()
    vector_cfg = ConfigManager().get_rag_config()["vector_db"]
    persist = Path(os.path.expandvars(vector_cfg["persist_directory"])).expanduser()
    if not persist.is_dir():
        raise FileNotFoundError(f"现有 Chroma 目录不存在: {persist}")
    client = chromadb.PersistentClient(path=str(persist))
    # 绑定只读取原文和元数据，不加载 BGE，也不执行向量检索或入库。
    db = client.get_collection(vector_cfg["collection_name"], embedding_function=None)
    known = {kb.name: str(kb.id) for kb in repo.list_knowledge_bases()}
    needed = {kb for row in questions for kb in row["knowledge_bases"]}
    if needed - set(known):
        raise RuntimeError(f"请先导入知识库：{sorted(needed-set(known))}")
    snapshots: dict[str, list[dict]] = {}
    for name in sorted(needed):
        data = db.get(
            where={"knowledge_base": {"$eq": known[name]}},
            include=["documents", "metadatas"],
        )
        snapshots[name] = [
            {"id": id_, "content": text, "metadata": meta}
            for id_, text, meta in zip(data["ids"], data["documents"], data["metadatas"])
        ]
        print(f"[索引] {name}: {len(snapshots[name])} chunks")
    output = bind_questions(questions, snapshots)
    dump_jsonl(args.output, output)
    counts = dict(Counter(q["binding_status"] for q in output))
    missed = [{"id":q["id"],"question":q["question"],"missing":q.get("unmatched_evidence")}
              for q in output if q["binding_status"]=="partial_or_missing"]
    report = {"questions":len(output),"binding_status_counts":counts,
              "missing_count":len(missed),"missing_examples":missed[:40],
              "warning":"仅完全绑定的自动锚点参与自动事实指标；既有 UUID 会与现有索引核对，不能核对的标为 invalid。"}
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("[结果]",args.output,"\n[统计]",json.dumps(counts,ensure_ascii=False),"\n[报告]",args.report)


if __name__ == "__main__":
    main()
