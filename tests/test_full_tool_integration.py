"""All original tool contracts; destructive and network operations use fake handlers only."""
import inspect
import json
from pathlib import Path
from dataclasses import replace

import pytest

from sys_agent.tool_registry import ToolRegistry, SAFE_TOOL_NAMES
from sys_agent.tool_executor import ToolExecutor
from sys_agent.tool_policy import ALL_TOOL_NAMES, READ_ONLY_TOOL_NAMES, APPROVAL_EFFECTS

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = [schema for file in (ROOT / 'sys_agent/toolkits').glob('*.json')
           for schema in json.loads(file.read_text(encoding='utf-8'))]


def example(schema):
    values = {'string': 'example', 'integer': 10, 'array': ['sample.txt'], 'boolean': True, 'number': 1.5}
    result = {name: values[spec['type']] for name, spec in schema['parameters']['properties'].items()
              if name in schema['parameters'].get('required', [])}
    if schema['name'] == 'generate_report_text':
        result['table_data'] = [{'count': 3, 'value': 1.5, 'empty': None, 'valid': True}]
    return result


def make_full(monkeypatch, tmp_path):
    monkeypatch.setenv('DEEPSHELL_ENABLE_ALL_TOOLS', '1')
    monkeypatch.setenv('DEEPSHELL_ENABLE_APPROVED_WRITE', '1')
    monkeypatch.setenv('DEEPSHELL_AGENT_WORKSPACE', str(tmp_path / 'workspace'))
    calls = []
    def fake(**args):
        calls.append(args)
        return dict(success=True, message='mock', arguments=args)
    return ToolExecutor(ToolRegistry.from_existing(SCHEMAS, {s['name']: fake for s in SCHEMAS})), calls


@pytest.mark.parametrize('schema', SCHEMAS, ids=lambda s: s['name'])
def test_every_tool_validates_and_routes_to_executor(monkeypatch, tmp_path, schema):
    executor, calls = make_full(monkeypatch, tmp_path)
    assert len(executor.registry.get_tool_schemas()) == 41
    assert executor.execute(schema['name'], {**example(schema), 'injected': True}).code == 'INVALID_ARGS'
    assert not calls
    arguments = example(schema)
    result = executor.execute(schema['name'], arguments)
    if schema['name'] in READ_ONLY_TOOL_NAMES:
        assert result.success and len(calls) == 1
    else:
        assert result.code == 'PENDING_APPROVAL' and not calls
        request_id = result.data['request_id']
        review = executor.get_pending_approval(request_id)
        assert review['tool'] == schema['name']
        frozen = json.loads(review['content'])['arguments']
        review['content'] = 'tampered GUI copy'
        arguments.clear()
        assert executor.resolve_pending_approval(request_id, True).success
        assert calls == [frozen]
        assert not executor.resolve_pending_approval(request_id, True).success
        with pytest.raises(PermissionError):
            executor.registry.get_function_map()[schema['name']](**frozen)


@pytest.mark.parametrize('decision', [False, 'true', 1, None, {}])
def test_generic_approval_deny_and_expiry(monkeypatch, tmp_path, decision):
    executor, calls = make_full(monkeypatch, tmp_path)
    ticket = executor.execute('shutdown_system', {})
    assert executor.resolve_pending_approval(ticket.data['request_id'], decision).code == 'APPROVAL_DENIED'
    assert not calls
    ticket = executor.execute('shutdown_system', {})
    executor.operation_approvals.ttl_seconds = -1
    assert executor.resolve_pending_approval(ticket.data['request_id'], True).code == 'APPROVAL_EXPIRED'
    assert not calls


@pytest.mark.parametrize('name,args', [
    ('batch_move_files', {'file_paths': [1], 'destination_directory': 'out'}),
    ('batch_move_files', {'file_paths': 'a.txt', 'destination_directory': 'out'}),
    ('close_application_by_pid', {'pid': True}),
    ('close_application_by_pid', {'pid': '123'}),
    ('generate_report_text', {'table_data': [{'value': float('nan')}], 'user_request': 'report'}),
    ('generate_report_text', {'table_data': [object()], 'user_request': 'report'}),
])
def test_strict_nested_and_integer_arguments(monkeypatch, tmp_path, name, args):
    executor, calls = make_full(monkeypatch, tmp_path)
    assert executor.execute(name, args).code == 'INVALID_ARGS'
    assert not calls


def test_registered_profile_and_feature_switch_cannot_be_bypassed(monkeypatch, tmp_path):
    executor, calls = make_full(monkeypatch, tmp_path)
    pending = executor.execute('run_program', {'command': 'echo approved command'})
    monkeypatch.setenv('DEEPSHELL_ENABLE_ALL_TOOLS', '0')
    assert executor.resolve_pending_approval(pending.data['request_id'], True).code == 'APPROVAL_DENIED'
    assert executor.execute('run_program', {'command': 'echo rejected'}).code == 'PERMISSION_DENIED'
    assert not calls


def test_handler_is_frozen_with_the_approved_request(monkeypatch, tmp_path):
    executor, calls = make_full(monkeypatch, tmp_path)
    ticket = executor.execute('run_program', {'command': 'original'})
    old = executor.registry.get('run_program')
    executor.registry._tools['run_program'] = replace(old, handler=lambda **_: pytest.fail('replacement executed'))
    assert executor.resolve_pending_approval(ticket.data['request_id'], True).success
    assert calls == [{'command': 'original'}]


def test_original_schemas_match_real_handler_signatures():
    from sys_agent.react_agent import ReActAgentController
    schemas, handlers = ReActAgentController._load_all_tools(None)
    assert {s['name'] for s in schemas} == ALL_TOOL_NAMES and len(schemas) == 40
    for schema in schemas:
        signature = inspect.signature(handlers[schema['name']])
        properties = schema['parameters']['properties']
        assert set(properties) <= set(signature.parameters)
        signature.bind(**example(schema))


def test_cache_plan_excludes_new_files_and_changed_targets(monkeypatch, tmp_path):
    from sys_agent import cache_cleanup
    root = tmp_path / 'cache'
    root.mkdir()
    original = root / 'old.txt'
    original.write_text('old')
    changed = root / 'changed.txt'
    changed.write_text('before')
    monkeypatch.setattr(cache_cleanup.platform, 'system', lambda: 'Windows')
    monkeypatch.setenv('TEMP', str(root))
    execute, preview = cache_cleanup.prepare_cache_cleanup()
    new = root / 'new.txt'
    new.write_text('new')
    changed.write_text('changed and must be skipped')
    assert str(new) not in preview['targets']
    assert original.exists()
    result = execute()
    assert result['success'] and not original.exists() and new.exists() and changed.exists()


def test_run_program_reports_actual_exit_code_without_running_a_shell(monkeypatch):
    from sys_agent.toolkits import system_tools
    from types import SimpleNamespace
    monkeypatch.setattr(system_tools.subprocess, 'run', lambda *_, **kwargs:
                        SimpleNamespace(returncode=1, stdout='', stderr='failed'))
    result = system_tools.run_program('never executed')
    assert result['success'] is False and result['returncode'] == 1 and result['stderr'] == 'failed'


def test_report_tool_uses_selected_model_only_after_approval(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from sys_agent.react_agent import ReActAgent
    from sys_agent.toolkits.data_analysis_tools import generate_report_text
    monkeypatch.setenv('DEEPSHELL_ENABLE_ALL_TOOLS', '1')
    monkeypatch.setenv('DEEPSHELL_ENABLE_APPROVED_WRITE', '1')
    model = SimpleNamespace(chat=Mock(return_value='generated report'))
    schema = next(s for s in SCHEMAS if s['name'] == 'generate_report_text')
    agent = ReActAgent('selected-model', [schema], {'generate_report_text': generate_report_text},
                       lambda *_: None, lambda *_: None, lambda *_: None, lambda *_: None,
                       lambda: False, model_manager=model)
    result = agent.executor.execute('generate_report_text', {'table_data': [{'sales': 5}], 'user_request': 'report'})
    assert result.code == 'PENDING_APPROVAL' and model.chat.call_count == 0
    completed = agent.executor.resolve_pending_approval(result.data['request_id'], True)
    assert completed.success and completed.data['report_text'] == 'generated report'
    assert model.chat.call_args.kwargs['model_name'] == 'selected-model'
    assert model.chat.call_args.kwargs['session_id'].startswith('agent_report_')


def test_concurrent_generic_approval_consumes_request_once(monkeypatch, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    executor, calls = make_full(monkeypatch, tmp_path)
    ticket = executor.execute('delete_file', {'path': str(tmp_path / 'fake.txt')})
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: executor.resolve_pending_approval(ticket.data['request_id'], True), range(2)))
    assert sum(result.success for result in outcomes) == 1 and len(calls) == 1


def test_approval_uses_resolved_path_even_after_working_directory_changes(monkeypatch, tmp_path):
    executor, calls = make_full(monkeypatch, tmp_path)
    first, second = tmp_path / 'first', tmp_path / 'second'
    first.mkdir()
    second.mkdir()
    monkeypatch.chdir(first)
    ticket = executor.execute('write_file', {'path': 'note.txt', 'content': 'approved content'})
    preview = executor.get_pending_approval(ticket.data['request_id'])
    assert str(first / 'note.txt') in json.loads(preview['content'])['arguments']['path']
    monkeypatch.chdir(second)
    assert executor.resolve_pending_approval(ticket.data['request_id'], True).success
    assert calls == [{'path': str(first / 'note.txt'), 'content': 'approved content'}]


def test_missing_table_cells_are_returned_as_valid_json(tmp_path):
    from sys_agent.toolkits.file_management_tools import read_table_data
    table = tmp_path / 'table.csv'
    table.write_text('name,value\none,1\ntwo,\n', encoding='utf-8')
    result = read_table_data(str(table))
    assert result['success'] and result['table_data'][1]['value'] is None
    json.dumps(result, allow_nan=False)
