"""无网络/模型的端到端评测协议测试。"""
import json

import pytest

from evals.benchmark_v1 import answer_experiment as experiment


def question(kind="answerable", bound=True):
    return {"id": "q", "question": "运行级别 2 和 5 的含义？", "task_type": kind,
            "split": "eval", "quality_tier": "explicit", "category": "runlevel",
            "binding_status": "bound" if bound else "no_source_anchor",
            "reference_answer": "参考答案秘密：两个必需事实",
            "evidence": [{"fact": "级别2", "quote": "事实二", "source": "s.pdf", "page": 7},
                         {"fact": "级别5", "quote": "事实五", "source": "s.pdf", "page": 7,
                          "alternatives": [{"quote": "同一事实替代", "source": "s.pdf", "page": 8}]}],
            "gold_evidence_groups": [{"chunk_ids": ["g2"]}, {"chunk_ids": ["g5", "g5alt"]}] if bound else []}


def row():
    return {"id": "q", "method": "hybrid_page", "label": "gold", "question": "运行级别 2 和 5 的含义？",
            "quality_tier": "explicit", "answer": "只回答级别2 [1]", "retrieval_ms": 1, "expand_ms": 2,
            "generation_ms": 10, "total_ms": 13, "judge_ms": 20, "kb_leak": 0,
            "evidence": [{"content": "实际原文", "source": "s.pdf", "page": 7, "chunk_id": "g2"}]}


def grade():
    return {"answer_correct": False, "abstained": None, "faithfulness": 1.0, "reason": "缺少级别5",
            "facts": [{"index": 1, "covered": True, "reason": "已回答"},
                      {"index": 2, "covered": False, "reason": "未回答"}],
            "citations": [{"index": 1, "supported": True, "reason": "有原文支持"}]}


def test_generation_only_sees_question_and_actual_evidence():
    sample = row() | question()
    sample["evidence"] = row()["evidence"]
    text = experiment.generation_prompt(sample)
    assert "实际原文" in text
    assert "参考答案秘密" not in text
    assert "gold_evidence_groups" not in text
    assert "g5alt" not in text


def test_gold_fact_and_or_variants_reach_judge_only():
    payload = experiment.judge_payload(row(), question())
    assert len(payload["required_facts"]) == 2
    assert len(payload["required_facts"][1]["variants"]) == 2
    assert "method" not in payload


def test_partial_fact_answer_is_not_full_credit():
    sample, q = row(), question()
    sample["judge"] = experiment.parse_grade(json.dumps(grade()), experiment.judge_payload(sample, q))
    metrics = experiment.grade_metrics(sample, q)
    assert metrics["answer_fact_completeness_judge"] == 0.5
    assert metrics["answer_accuracy_judge"] == 0


@pytest.mark.parametrize("field,value", [("faithfulness", float("nan")), ("faithfulness", True),
                                         ("answer_correct", 1), ("abstained", True),
                                         ("facts", []), ("citations", []), ("reason", None)])
def test_malformed_judgment_is_rejected(field, value):
    bad = grade() | {field: value}
    with pytest.raises(ValueError):
        experiment.parse_grade(json.dumps(bad), experiment.judge_payload(row(), question()))


def test_duplicate_fact_or_citation_is_rejected():
    for field in ("facts", "citations"):
        bad = grade()
        bad[field].append(bad[field][0])
        with pytest.raises(ValueError):
            experiment.parse_grade(json.dumps(bad), experiment.judge_payload(row(), question()))


def test_out_of_range_citation_cannot_be_approved_by_judge():
    sample = row() | {"answer": "答案 [99]"}
    out = grade()
    out["citations"][0]["index"] = 99
    sample["judge"] = experiment.parse_grade(json.dumps(out), experiment.judge_payload(sample, question()))
    metrics = experiment.grade_metrics(sample, question())
    assert metrics["citation_accuracy_judge"] == 0
    assert metrics["citation_ids_valid"] is False


def test_missing_citations_have_zero_accuracy_for_gold():
    sample = row() | {"answer": "无引用的答案"}
    out = grade() | {"citations": []}
    sample["judge"] = experiment.parse_grade(json.dumps(out), experiment.judge_payload(sample, question()))
    assert experiment.grade_metrics(sample, question())["citation_accuracy_judge"] == 0


def test_negative_and_unbound_have_different_scoring_scopes():
    for kind, expected in (("negative", True), ("answerable", None)):
        q = question(kind=kind, bound=False)
        sample = row()
        payload = experiment.judge_payload(sample, q)
        assert payload["required_facts"] == []
        out = grade() | {"facts": [], "answer_correct": None, "abstained": expected}
        sample["judge"] = experiment.parse_grade(json.dumps(out), payload)
        metrics = experiment.grade_metrics(sample, q)
        assert metrics["answer_accuracy_judge"] is None
        assert metrics["negative_refusal_rate_judge"] == (1 if expected else None)


def test_failed_judge_can_retry_without_generating_again(monkeypatch):
    calls = []
    def fake_invoke(llm, system, prompt):
        calls.append(llm)
        payload = json.loads(prompt)
        if "required_facts" in payload:
            return json.dumps(grade() | {"citations": []}), {}
        assert "reference_answer" not in payload and "required_facts" not in payload
        return json.dumps({"citations": grade()["citations"], "reason": "支持"}), {}
    monkeypatch.setattr(experiment, "invoke", fake_invoke)
    sample = row() | {"judge_error": {"type": "TimeoutError"}}
    result = experiment.complete_case(sample, question(), "generator", "judge")
    assert calls == ["judge", "judge"]
    assert result["answer"] == sample["answer"]
    assert result["generation_ms"] == 10
    assert result["total_ms"] == 13
    assert "judge_error" not in result


def test_citation_retry_reuses_successful_quality_grade(monkeypatch):
    calls = []
    def fake_invoke(llm, system, prompt):
        calls.append(json.loads(prompt))
        return json.dumps({"citations": grade()["citations"], "reason": "支持"}), {}
    monkeypatch.setattr(experiment, "invoke", fake_invoke)
    sample = row() | {"quality_grade": grade() | {"citations": []}, "judge_error": {"type": "TimeoutError"}}
    result = experiment.complete_case(sample, question(), "generator", "judge")
    assert len(calls) == 1
    assert "reference_answer" not in calls[0]
    assert "judge_error" not in result


def test_generation_failure_never_calls_judge(monkeypatch):
    calls = []
    def fail(llm, system, prompt):
        calls.append(llm)
        raise TimeoutError("should not expose secret request info")
    monkeypatch.setattr(experiment, "invoke", fail)
    sample = row()
    sample.pop("answer")
    result = experiment.complete_case(sample, question(), "generator", "judge")
    assert calls == ["generator"]
    assert result["generation_error"] == {"type": "TimeoutError"}
    assert "answer_metrics" not in result


def test_errors_are_counted_separately_from_valid_metric_denominators():
    good = row()
    good["judge"] = grade()
    good["answer_metrics"] = experiment.grade_metrics(good, question())
    failed = row() | {"id": "bad", "judge_error": {"type": "TimeoutError"}}
    summary = experiment.summarize([good, failed])["hybrid_page"]
    assert summary["judge_errors"] == 1
    assert summary["graded"] == 1
    assert summary["metrics"]["answer_accuracy_judge"] == {"value": 0, "n": 1}
    assert summary["metrics"]["negative_refusal_rate_judge"] == {"value": None, "n": 0}


def test_resume_refuses_overwrite_and_changed_inputs(tmp_path):
    manifest = {"question_ids": ["q"], "methods": list(experiment.METHODS), "dataset_sha256": "frozen"}
    assert experiment.load_resume(tmp_path, manifest, False) == []
    with pytest.raises(ValueError):
        experiment.load_resume(tmp_path, manifest, False)
    assert experiment.load_resume(tmp_path, manifest, True) == []
    with pytest.raises(ValueError):
        experiment.load_resume(tmp_path, manifest | {"dataset_sha256": "changed"}, True)


def test_resume_rejects_duplicate_records(tmp_path):
    manifest = {"question_ids": ["q"], "methods": list(experiment.METHODS)}
    experiment.load_resume(tmp_path, manifest, False)
    (tmp_path / "details.jsonl").write_text((json.dumps(row()) + "\n") * 2, encoding="utf-8")
    with pytest.raises(ValueError):
        experiment.load_resume(tmp_path, manifest, True)


@pytest.mark.parametrize("content,finish,code", [("", "stop", "empty_output"),
                                                ("未完整回答", "length", "truncated_output")])
def test_empty_or_truncated_output_is_not_silently_graded(content, finish, code):
    from langchain_core.messages import AIMessage
    class LLM:
        def invoke(self, messages):
            return AIMessage(content=content, response_metadata={"finish_reason": finish},
                             usage_metadata={"input_tokens": 5, "output_tokens": 20, "total_tokens": 25})
    with pytest.raises(experiment.ModelOutputError) as caught:
        experiment.invoke(LLM(), "system", "prompt")
    error = experiment.safe_error(caught.value)
    assert error["code"] == code
    assert error["usage"]["output_tokens"] == 20
