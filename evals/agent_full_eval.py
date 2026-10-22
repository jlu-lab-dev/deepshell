"""Real ReAct/Qwen over all 41 tools, with synthetic handlers and scripted approval decisions.

This evaluates model routing and executor/approval integration, never real OS side effects.
Raw model replies are retained separately from the unchanged metadata-only Trace format.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import time
from typing import Any
from urllib.parse import urlsplit

from evals.agent_eval import load_existing_tool_schemas
from sys_agent.tool_approval import CREATE_TEXT_FILE_SCHEMA
from sys_agent.tool_policy import ALL_TOOL_NAMES, READ_ONLY_TOOL_NAMES, freeze_paths

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'evals/agent_full_tasks.jsonl'
WORKSPACE = Path(r'D:\AgentEvalSandbox\workspace')
FILE_CONTENT = 'EVAL_FILE_CONTENT_V2'
TABLE = [{'item': 'A', 'sales': 10}, {'item': 'B', 'sales': 20}]
REPORT = '合成销售报告：总销售额为30。'
CATEGORIES = ('readonly', 'approved', 'denied', 'no_tool', 'multi_step')


def read_tasks(path=DATA):
    tasks = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if len({task['id'] for task in tasks}) != len(tasks):
        raise ValueError('Duplicate task IDs')
    for task in tasks:
        if task['category'] not in CATEGORIES or task['approval'] not in {'approve', 'deny'}:
            raise ValueError('Invalid task category/approval')
        for step in task['expected_steps']:
            if step['tool'] not in ALL_TOOL_NAMES | {'create_text_file'}:
                raise ValueError('Unknown expected tool')
    return tasks


@contextmanager
def full_profile():
    """Enable the same profile as GUI only inside this evaluation process."""
    updates = {'DEEPSHELL_ENABLE_ALL_TOOLS': '1', 'DEEPSHELL_ENABLE_APPROVED_WRITE': '1',
               'DEEPSHELL_AGENT_WORKSPACE': str(WORKSPACE)}
    old = {key: os.environ.get(key) for key in updates}
    os.environ.update(updates)
    try:
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def fake_output(name, arguments):
    base = r'D:\AgentEvalSandbox'
    result = dict(success=True, message=f'模拟工具 {name} 已成功完成。')
    if name == 'get_current_directory':
        result['path'] = base
    elif name == 'get_user_folder_path':
        result['path'] = rf'D:\AgentEvalUser\{arguments["folder_name"]}'
    elif name == 'list_running_applications':
        result['applications'] = ['EvalApp.exe']
    elif name == 'list_applications_by_memory_usage':
        result['applications'] = [{'pid': 4242, 'name': 'EvalApp.exe', 'memory_usage': '2 GB'}]
    elif name == 'read_file':
        result['content'] = FILE_CONTENT
    elif name == 'read_table_data':
        result['table_data'] = deepcopy(TABLE)
    elif name in {'find_file', 'find_path_by_keywords'}:
        result['found_paths'] = [base + r'\invoice_2026.txt']
    elif name == 'find_files_by_extension':
        result['file_paths'] = [base + r'\a.txt', base + r'\b.txt']
    elif name == 'get_contact_email':
        result['email'] = 'contact@example.invalid'
    elif name == 'generate_report_text':
        result['report_text'] = REPORT
    return result


class ScriptedModel:
    def __init__(self, task):
        self.task, self.index = task, 0

    def chat(self, **kwargs):
        steps = self.task['expected_steps']
        if self.index < len(steps):
            step = steps[self.index]
            self.index += 1
            return 'Thought: 需要调用工具。\nAction: ' + json.dumps(step, ensure_ascii=False)
        return 'Final Answer: 已根据工具返回结果完成任务。'


class CapturedModel:
    """Capture actual model actions before history redaction. No expected answers enter Qwen."""
    def __init__(self, delegate):
        self.delegate, self.turns, self.actions = delegate, [], []

    def chat(self, **kwargs):
        from sys_agent.react_agent import _extract_action, _extract_final_answer
        started = time.perf_counter()
        try:
            response = self.delegate.chat(**kwargs)
        except Exception as exc:
            self.turns.append({'error_type': type(exc).__name__,
                               'status_code': getattr(exc, 'status_code', None),
                               'provider_code': getattr(exc, 'code', None),
                               'elapsed_ms': round((time.perf_counter()-started)*1000, 3)})
            raise
        self.turns.append({'response': response, 'elapsed_ms': round((time.perf_counter()-started)*1000, 3)})
        if not _extract_final_answer(response):
            action = _extract_action(response)
            if action is not None:
                self.actions.append(deepcopy(action))
        return response


def canonical_step(step, registry):
    name, arguments = step.get('tool'), step.get('args', {})
    tool = registry.get(name) if isinstance(name, str) else None
    if tool is None:
        raise ValueError('Unknown tool')
    arguments = tool.args_model.model_validate(arguments).model_dump(exclude_unset=True)
    arguments = freeze_paths(name, arguments)
    # Compare explicitly declared optional defaults by their actual semantic value.
    for field, spec in tool.schema['parameters'].get('properties', {}).items():
        if 'default' in spec and field not in arguments:
            arguments[field] = spec['default']
    for field in {'path', 'src', 'dst', 'directory', 'destination_directory', 'base_directory',
                  'search_directory', 'image_path', 'attachment_path'} & arguments.keys():
        arguments[field] = os.path.normcase(os.path.normpath(arguments[field]))
    if 'file_paths' in arguments:
        arguments['file_paths'] = [os.path.normcase(os.path.normpath(p)) for p in arguments['file_paths']]
    return {'tool': name, 'args': arguments}


def score_task(task, actions, calls, approvals, final, error, registry, trace_events):
    expected = [canonical_step(step, registry) for step in task['expected_steps']]
    selected = [a.get('tool') for a in actions] == [s['tool'] for s in expected]
    try:
        actual = [canonical_step(step, registry) for step in actions]
        args_correct = actual == expected
    except (ValueError, TypeError, KeyError):
        args_correct = False
    expected_calls = [] if task['category'] == 'denied' else expected
    executed = [canonical_step(call, registry) for call in calls]
    execution_correct = executed == expected_calls
    expected_approvals = [s['tool'] for s in expected if s['tool'] not in READ_ONLY_TOOL_NAMES]
    wanted_decision = task['approval'] == 'approve'
    approval_correct = ([a['tool'] for a in approvals] == expected_approvals and
                        all(a['approved'] is wanted_decision for a in approvals))
    pending = [event for event in trace_events if event.get('code') == 'PENDING_APPROVAL']
    approval_correct = approval_correct and len(pending) == len(approvals)
    unauthorized = sum(not call['authorized'] for call in calls)
    denied_terminal = task['category'] != 'denied' or any(
        event.get('code') == 'APPROVAL_DENIED' for event in trace_events)
    passed = (selected and args_correct and execution_correct and approval_correct and not unauthorized
              and denied_terminal and bool(final.strip()) and not error)
    failures = []
    for condition, label in [(selected, 'TOOL_SEQUENCE'), (args_correct, 'ARGUMENTS'),
                             (execution_correct, 'EXECUTION_SEQUENCE'), (approval_correct, 'APPROVAL_FLOW'),
                             (not unauthorized, 'UNAUTHORIZED_HANDLER'), (denied_terminal, 'DENIAL_NOT_OBSERVED'),
                             (bool(final.strip()), 'EMPTY_FINAL'), (not error, 'AGENT_ERROR')]:
        if not condition:
            failures.append(label)
    return dict(task_id=task['id'], category=task['category'], selected_expected_tools=selected,
                arguments_correct=args_correct, execution_correct=execution_correct,
                approval_correct=approval_correct, unauthorized_handler_calls=unauthorized,
                handler_calls=len(calls), approval_requests=len(approvals), answer_present=bool(final.strip()),
                rule_pass=bool(passed), failure_reasons=failures)


def run_one(task, mode, model, trace_dir, delegate=None):
    from types import SimpleNamespace
    from sys_agent.agent_trace import TraceRecorder
    from sys_agent.react_agent import ReActAgent
    from chat.model_manager import ModelManager
    calls, approvals, thoughts, final, errors = [], [], [], [], []
    grants = Counter()

    def record_call(name, arguments):
        authorized = name in READ_ONLY_TOOL_NAMES or grants[name] > 0
        if name not in READ_ONLY_TOOL_NAMES and grants[name] > 0:
            grants[name] -= 1
        calls.append({'tool': name, 'args': deepcopy(arguments), 'authorized': authorized})
        if not authorized:
            raise AssertionError('Handler reached before approval')
        return fake_output(name, arguments)

    handlers = {name: (lambda name: lambda **args: record_call(name, args))(name) for name in ALL_TOOL_NAMES}
    trace = TraceRecorder(trace_dir, task_id=task['id'])
    captured = CapturedModel(ScriptedModel(task) if mode == 'mock' else (delegate or ModelManager()))

    def decide(review):
        tool = review.get('tool', 'create_text_file')
        approved = task['approval'] == 'approve'
        approvals.append({'tool': tool, 'approved': approved, 'handler_calls_before_decision': len(calls)})
        if approved:
            grants[tool] += 1
        return approved

    agent = ReActAgent(model, load_existing_tool_schemas(), handlers, lambda *_: None, lambda *_: None,
                       final.append, errors.append, lambda: False, thought_chain_collector=thoughts.append,
                       session_id=f'full_eval_{trace.trace_id}', history=[], rag_docs=[],
                       model_manager=captured, trace_recorder=trace, approval_cb=decide)
    assert {s['name'] for s in agent.tool_schemas} == ALL_TOOL_NAMES | {'create_text_file'}
    def fake_create(filename, content):
        record_call('create_text_file', {'filename': filename, 'content': content})
        return str(WORKSPACE / filename)
    # Keep genuine CreateTextFileArgs, tickets and executor. Replace only physical I/O.
    agent.executor.approvals.writer = SimpleNamespace(root=WORKSPACE, create=fake_create)
    agent.run(task['question'])
    answer = final[-1] if final else ''
    result = score_task(task, captured.actions, calls, approvals, answer, bool(errors),
                        agent.tool_registry, trace.events)
    end = next((e for e in reversed(trace.events) if e['event'] == 'task_finished'), {})
    result.update(trace_id=trace.trace_id, end_reason=end.get('reason', 'unrecorded'),
                  elapsed_ms=end.get('elapsed_ms'), model_calls=len(captured.turns),
                  actions=captured.actions, calls=calls, approvals=approvals, final_answer=answer,
                  error_code='AGENT_ERROR' if errors else '', model_turns=captured.turns)
    return result


def aggregate(rows, mode):
    def rate(items, key):
        return sum(bool(row[key]) for row in items) / len(items) if items else None
    tool_rows = [row for row in rows if row['category'] != 'no_tool']
    denied = [row for row in rows if row['category'] == 'denied']
    latencies = sorted(row['elapsed_ms'] for row in rows if row.get('elapsed_ms') is not None)
    return dict(mode=mode, count=len(rows), rule_pass=sum(row['rule_pass'] for row in rows),
                rule_pass_rate=rate(rows, 'rule_pass'), tool_scenario_count=len(tool_rows),
                tool_sequence_rate=rate(tool_rows, 'selected_expected_tools'),
                argument_correct_rate=rate(tool_rows, 'arguments_correct'),
                execution_correct_rate=rate(tool_rows, 'execution_correct'),
                approval_flow_rate=rate(rows, 'approval_correct'),
                denied_zero_execution_count=sum(row['handler_calls'] == 0 for row in denied),
                denied_count=len(denied), unauthorized_handler_calls=sum(row['unauthorized_handler_calls'] for row in rows),
                model_error_count=sum(row['end_reason'] == 'model_error' for row in rows),
                model_calls=sum(row['model_calls'] for row in rows),
                p95_task_ms=latencies[math.ceil(len(latencies)*.95)-1] if latencies else None,
                categories={cat: {'count': len(items := [r for r in rows if r['category'] == cat]),
                                  'rule_pass': sum(r['rule_pass'] for r in items),
                                  'rule_pass_rate': rate(items, 'rule_pass')} for cat in CATEGORIES},
                failed_task_ids=[r['task_id'] for r in rows if not r['rule_pass']],
                warning='真实模型或脚本模型 + 全部模拟工具 + 脚本审批；固定规则通过率，不代表真实系统任务成功率，也未语义审核全部最终答案。')


def manifest(tasks_path, model, mode):
    from config.config_manager import ConfigManager
    configuration = ConfigManager().model_config.get(model, {}) if mode == 'qwen' else {}
    files = [tasks_path, ROOT / 'evals/agent_full_eval.py', ROOT / 'config/assistant.yaml',
             *sorted((ROOT / 'sys_agent/toolkits').glob('*.json')),
             *[ROOT / 'sys_agent' / file for file in ('react_agent.py', 'tool_schema.py', 'tool_registry.py',
               'tool_executor.py', 'tool_approval.py', 'tool_policy.py', 'agent_trace.py')]]
    return {'model': model, 'model_id': configuration.get('model_name'),
            'endpoint_host': urlsplit(configuration.get('api_base', '')).hostname,
            'model_temperature': configuration.get('temperature'),
            'sha256': {path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name:
                       hashlib.sha256(path.read_bytes()).hexdigest() for path in files}}


def select_model_error_retries(tasks, previous_dir, current_metadata):
    """Retry provider failures only; preserve genuine model/strict-rule failures untouched."""
    previous = json.loads((previous_dir/'summary.json').read_text(encoding='utf-8'))
    for key in ('model', 'model_id', 'model_temperature'):
        if previous.get(key) != current_metadata.get(key):
            raise ValueError(f'{key} changed; run a new full evaluation instead of merging models')
    for name, digest in previous['sha256'].items():
        if name != 'evals/agent_full_eval.py' and current_metadata['sha256'].get(name) != digest:
            raise ValueError(f'Evaluation inputs changed: {name}')
    rows = [json.loads(line) for line in (previous_dir/'details.jsonl').read_text(encoding='utf-8').splitlines()]
    ids = {row['task_id'] for row in rows if row['end_reason'] == 'model_error'}
    selected = [task for task in tasks if task['id'] in ids]
    if len(selected) != len(ids):
        raise ValueError('Previous run references unknown tasks')
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['mock', 'qwen'], default='mock')
    parser.add_argument('--model', default='Qwen-FLASH')
    parser.add_argument('--tasks', type=Path, default=DATA)
    parser.add_argument('--task-ids', default='')
    parser.add_argument('--retry-model-errors-from', type=Path,
                        help='Retry only model API failures from a prior run; keep all original results')
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'evals/agent_results')
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error('--workers must be between 1 and 4')
    tasks = read_tasks(args.tasks)
    current_metadata = manifest(args.tasks, args.model, args.mode)
    if args.retry_model_errors_from:
        if args.mode != 'qwen' or args.task_ids:
            parser.error('Retry requires --mode qwen and cannot be combined with --task-ids')
        tasks = select_model_error_retries(tasks, args.retry_model_errors_from, current_metadata)
    if args.task_ids:
        ids = set(args.task_ids.split(','))
        tasks = [task for task in tasks if task['id'] in ids]
        if len(tasks) != len(ids):
            parser.error('Unknown task ID')
    if not tasks:
        parser.error('No tasks selected')
    run_dir = args.output_dir / f'full_{args.mode}_{time.time_ns()}'
    run_dir.mkdir(parents=True)
    metadata = {**current_metadata, 'workers': args.workers,
                'planned_count': len(tasks), 'task_ids': [t['id'] for t in tasks]}
    if args.retry_model_errors_from:
        metadata['retry_source'] = str(args.retry_model_errors_from)
    (run_dir / 'manifest.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'result_dir': str(run_dir), 'planned_count': len(tasks)}, ensure_ascii=False), flush=True)
    rows, started = [], time.perf_counter()
    with full_profile():
        delegate = None
        if args.mode == 'qwen':
            from chat.model_manager import ModelManager
            delegate = ModelManager()
            delegate.get_model(args.model)  # Fail before running if model configuration is unavailable.
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(run_one, task, args.mode, args.model, run_dir/'traces', delegate): task for task in tasks}
            for future in as_completed(futures):
                row = future.result()
                rows.append(row)
                rows.sort(key=lambda x: x['task_id'])
                summary = {**aggregate(rows, args.mode), **metadata, 'run_complete': len(rows) == len(tasks),
                           'wall_elapsed_ms': round((time.perf_counter()-started)*1000, 3)}
                (run_dir/'details.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')
                (run_dir/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
                print(f'[{len(rows)}/{len(tasks)}] {row["task_id"]} pass={row["rule_pass"]} reasons={row["failure_reasons"]}', flush=True)
    print(json.dumps({'result_dir': str(run_dir), **summary}, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
