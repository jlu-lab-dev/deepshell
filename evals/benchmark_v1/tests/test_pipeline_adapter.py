"""新增评测适配器的事实、来源及生成边界测试。"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from evals.retrieval import pipeline_eval
from evals.benchmark_v1.evaluate import summarize
from evals.benchmark_v1.bind_gold import read_jsonl
from pathlib import Path
from collections import Counter
import json


def sample():
    question = {
        "id": "test", "split": "dev", "question": "运行级别 2 和 5？",
        "task_type": "answerable", "knowledge_bases": ["server"],
        "reference_answer": "不能作为模型输入的参考答案", "evidence": [],
        "gold_evidence_groups": [
            {"fact": "级别2", "chunk_ids": ["two"]},
            {"fact": "级别5", "chunk_ids": ["five"]},
        ],
    }
    seed = {"chroma_id": "two", "content": "级别2" + "原文" * 160, "metadata": {
        "knowledge_base": "kb-id", "doc_id": "doc", "source": "server.pdf", "page": 6
    }}
    sibling = {"knowledge_base": "kb-id", "doc_id": "doc", "source": "server.pdf", "page": 6}
    collection = Mock()
    collection.get.return_value = {
        "ids": ["two", "five"], "documents": [seed["content"], "级别5"],
        "metadatas": [seed["metadata"], sibling],
    }
    rag = SimpleNamespace(vector_db=SimpleNamespace(_collection=collection))
    return question, seed, rag


def test_adapter_scores_expanded_context_beyond_original_k(monkeypatch):
    question, seed, rag = sample()
    search = Mock(return_value=[seed])
    monkeypatch.setattr(pipeline_eval, "search_one", search)
    row = pipeline_eval.run_one(rag, question, "rrf_page", ["kb-id"], {"kb-id": "server"}, k=1)
    search.assert_called_once_with(rag, "rrf", question["question"], 1, ["kb-id"])
    assert row["base_metrics"]["fact_coverage"] == 0.5
    assert row["final_metrics"]["fact_coverage"] == 1
    assert row["final_metrics"]["fact_all"]
    assert row["context_chunks"] == 2
    assert len(row["evidence"][0]["content"]) > 240
    assert row["context_chars"] == len(seed["content"]) + len("级别5")
    assert "answer" not in row and row["generation_metrics"] == {}


def test_baseline_does_not_expand_and_enforces_k(monkeypatch):
    question, seed, rag = sample()
    monkeypatch.setattr(pipeline_eval, "search_one", Mock(return_value=[seed, seed]))
    row = pipeline_eval.run_one(rag, question, "hybrid", ["kb-id"], {"kb-id": "server"}, k=1)
    assert row["context_chunks"] == 1
    rag.vector_db._collection.get.assert_not_called()


def test_generation_uses_full_actual_evidence_and_no_reference_answer(monkeypatch):
    question, seed, rag = sample()
    monkeypatch.setattr(pipeline_eval, "search_one", Mock(return_value=[seed]))
    llm = Mock()
    llm.invoke.return_value = SimpleNamespace(content="级别2 [1]；级别5 [2]")
    row = pipeline_eval.run_one(rag, question, "hybrid_page", ["kb-id"], {"kb-id": "server"}, llm=llm)
    prompt = llm.invoke.call_args.args[0][1].content
    assert seed["content"] in prompt and "[2] 文件：server.pdf" in prompt
    assert question["reference_answer"] not in prompt
    assert row["generation_metrics"]["citation_ids_valid"]
    assert "generation_ms" in row


def test_answer_heuristics_and_content_blocks():
    assert pipeline_eval.extract_answer(SimpleNamespace(content=[
        {"type": "text", "text": "回答"}, " [1]"
    ]))[0] == "回答 [1]"
    assert not pipeline_eval.generation_metrics({"task_type": "answerable"}, "回答 [3]", 2)["citation_ids_valid"]
    question = {"task_type": "answerable", "answer_fact_patterns": [
        {"any_of": ["Ctrl+Alt+T"]}, {"any_of": ["其他事实"]}
    ]}
    assert pipeline_eval.generation_metrics(question, "Ctrl + Alt + T [1]", 1)["answer_fact_coverage_heuristic"] == 0.5


def test_summaries_keep_tiers_and_kb_leaks_visible(monkeypatch):
    question, seed, rag = sample()
    monkeypatch.setattr(pipeline_eval, "search_one", Mock(return_value=[seed]))
    row = pipeline_eval.run_one(rag, question, "rrf", ["kb-id"], {"kb-id": "server"})
    row.update(binding_status="bound", category="runlevel", quality_tier="explicit")
    other = {**row, "quality_tier": "silver", "final_metrics": {"kb_leak": True}}
    report = summarize([row, other])
    assert report["methods"]["rrf"]["kb_leak_queries"] == 1
    assert set(report["by_quality_tier"]) == {"explicit", "silver"}
    assert report["by_quality_tier"]["explicit"]["methods"]["rrf"]["final_fact_coverage"]["n"] == 1


def test_release_files_match_manifest_and_splits():
    data = Path(__file__).resolve().parents[1] / "data"
    all_rows = read_jsonl(data / "enterprise_all.jsonl")
    manifest = json.loads((data / "manifest.json").read_text(encoding="utf-8"))
    assert len(all_rows) == manifest["total"] == 364
    assert dict(Counter(q["quality_tier"] for q in all_rows)) == manifest["counts_by_tier"]
    for split in ("dev", "eval"):
        assert read_jsonl(data / f"enterprise_{split}.jsonl") == [q for q in all_rows if q["split"] == split]


def test_judge_abstention_only_counts_negative_questions():
    from evals.benchmark_v1.judge import summarize_judgments

    grade = {'answer_correctness': 1, 'faithfulness': 1, 'citation_support': 1, 'abstention_quality': 1}
    rows = [
        {'method': 'hybrid', 'task_type': 'answerable', 'judge': grade},
        {'method': 'hybrid', 'task_type': 'negative', 'judge': {**grade, 'abstention_quality': 0.5}},
        {'method': 'hybrid', 'task_type': 'negative', 'judge': {'error': 'failed'}},
    ]
    summary = summarize_judgments(rows)['hybrid']
    assert summary['abstention_quality'] == {'value': 0.5, 'n': 1}
    assert summary['answer_correctness'] == {'value': 1.0, 'n': 2}
    assert (summary['judged'], summary['errors']) == (2, 1)


def test_judge_boolean_is_not_a_numeric_grade():
    from evals.benchmark_v1.judge import parse_grade

    with pytest.raises(ValueError):
        parse_grade(json.dumps({
            'answer_correctness': 1, 'faithfulness': 1, 'citation_support': 1,
            'abstention_quality': True, 'reason': 'invalid'
        }))
