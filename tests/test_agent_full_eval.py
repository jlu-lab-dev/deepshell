"""All full-tool evaluation checks are offline and never initialize a real client."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from evals import agent_full_eval as evaluation
from sys_agent.tool_policy import ALL_TOOL_NAMES, READ_ONLY_TOOL_NAMES


def test_fixed_suite_has_full_coverage_and_distinct_approval_branches():
    tasks = evaluation.read_tasks()
    assert len(tasks) == 84
    single = [task for task in tasks if task['category'] in {'readonly', 'approved'}]
    assert {task['expected_steps'][0]['tool'] for task in single} == ALL_TOOL_NAMES | {'create_text_file'}
    denied = [task for task in tasks if task['category'] == 'denied']
    assert len(denied) == 31
    assert {t['expected_steps'][0]['tool'] for t in denied} == (ALL_TOOL_NAMES - READ_ONLY_TOOL_NAMES) | {'create_text_file'}


@pytest.mark.parametrize('task', evaluation.read_tasks(), ids=lambda task: task['id'])
def test_all_mock_scenarios_use_real_executor_without_os_handlers(task, monkeypatch, tmp_path):
    from sys_agent import react_agent
    monkeypatch.setattr(react_agent, 'ModelManager', lambda: pytest.fail('Offline test initialized online models'))
    with evaluation.full_profile():
        result = evaluation.run_one(task, 'mock', 'fake', tmp_path / 'traces')
    assert result['rule_pass'], result['failure_reasons']
    assert not result['unauthorized_handler_calls']
    trace = (tmp_path/'traces'/f'{result["trace_id"]}.jsonl').read_text(encoding='utf-8')
    assert 'AgentEvalSandbox' not in trace and 'Hello Workspace' not in trace
    assert json.loads(trace.splitlines()[-1])['event'] == 'task_finished'
    if task['category'] == 'denied':
        assert not result['calls'] and len(result['approvals']) == 1


def test_wrong_arguments_do_not_get_credit_and_original_actions_are_retained(tmp_path):
    task = next(t for t in evaluation.read_tasks() if t['expected_steps'] and
                t['expected_steps'][0]['tool'] == 'close_application_by_pid')
    responses = iter(['Action: {"tool":"close_application_by_pid","args":{"pid":4243}}',
                      'Final Answer: 已完成。'])
    with evaluation.full_profile():
        result = evaluation.run_one(task, 'qwen', 'fake', tmp_path, SimpleNamespace(chat=lambda **_: next(responses)))
    assert not result['rule_pass'] and 'ARGUMENTS' in result['failure_reasons']
    assert result['actions'][0]['args'] == {'pid': 4243}
    assert result['calls'][0]['args'] == {'pid': 4243}


def test_api_error_cannot_be_scored_as_a_successful_denial(tmp_path):
    task = next(t for t in evaluation.read_tasks() if t['category'] == 'denied')
    def failure(**kwargs):
        raise ConnectionError('synthetic failure')
    with evaluation.full_profile():
        row = evaluation.run_one(task, 'qwen', 'fake', tmp_path, SimpleNamespace(chat=failure))
    assert not row['rule_pass'] and row['end_reason'] == 'model_error'
    assert row['model_turns'][0]['error_type'] == 'ConnectionError'
    assert evaluation.aggregate([row], 'qwen')['model_error_count'] == 1


def test_full_eval_capture_preserves_stateless_agent_calls():
    def forbidden(**kwargs):
        pytest.fail('Full-tool wrapper reintroduced model memory')
    captured=evaluation.CapturedModel(SimpleNamespace(chat=forbidden,
        chat_once=lambda **kwargs:'Final Answer: done'))
    assert captured.chat(messages=['query']) == 'Final Answer: done'
    assert len(captured.turns)==1


def test_aggregate_denominators_and_empty_results():
    summary = evaluation.aggregate([], 'mock')
    assert summary['rule_pass_rate'] is None and summary['p95_task_ms'] is None


def test_profile_restores_environment(monkeypatch):
    import os
    monkeypatch.setenv('DEEPSHELL_ENABLE_ALL_TOOLS', '0')
    with evaluation.full_profile():
        assert os.environ['DEEPSHELL_ENABLE_ALL_TOOLS'] == '1'
    assert os.environ['DEEPSHELL_ENABLE_ALL_TOOLS'] == '0'


def test_retry_selects_only_api_failures_not_genuine_model_failures(tmp_path):
    tasks = evaluation.read_tasks()
    metadata = {'model': 'fake', 'model_id': 'fixed', 'model_temperature': .3,
                'sha256': {'evals/agent_full_eval.py': 'old-runner', 'config/assistant.yaml': 'fixed-prompt'}}
    (tmp_path/'summary.json').write_text(json.dumps(metadata), encoding='utf-8')
    rows = [{'task_id': tasks[0]['id'], 'end_reason': 'completed', 'rule_pass': False},
            {'task_id': tasks[1]['id'], 'end_reason': 'model_error', 'rule_pass': False}]
    (tmp_path/'details.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows), encoding='utf-8')
    current = deepcopy(metadata)
    current['sha256']['evals/agent_full_eval.py'] = 'retry-enabled-runner'
    assert evaluation.select_model_error_retries(tasks, tmp_path, current) == [tasks[1]]


@pytest.mark.parametrize('change', ['model_id', 'prompt'])
def test_retry_refuses_to_mix_changed_models_or_prompts(tmp_path, change):
    metadata = {'model': 'fake', 'model_id': 'fixed', 'model_temperature': .3,
                'sha256': {'config/assistant.yaml': 'fixed-prompt'}}
    (tmp_path/'summary.json').write_text(json.dumps(metadata), encoding='utf-8')
    current = deepcopy(metadata)
    if change == 'prompt':
        current['sha256']['config/assistant.yaml'] = 'changed'
    else:
        current['model_id'] = 'different-model'
    with pytest.raises(ValueError):
        evaluation.select_model_error_retries(evaluation.read_tasks(), tmp_path, current)
