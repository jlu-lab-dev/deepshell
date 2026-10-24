"""Offline recovery and real temporary-file acceptance; no live model or OS tools."""
import json
from types import SimpleNamespace as NS

import pytest

from evals.agent_eval import load_existing_tool_schemas
from evals.agent_full_eval import FILE_CONTENT
from evals.agent_state import path
from sys_agent.react_agent import ReActAgent
from sys_agent.tool_executor import ToolExecutor
from sys_agent.tool_registry import ToolRegistry
from sys_agent.toolkits import file_management_tools as files
from test_agent_state_v3 import ROOT, environment, approved
from test_native_fc_session import CONFIG, FakeClient, text_response


def reply(turn, *actions):
    calls = [NS(id=f'call_{turn}_{i}', type='function',
                function=NS(name=name, arguments=json.dumps(args)))
             for i, (name, args) in enumerate(actions)]
    return NS(choices=[NS(message=NS(content=None, tool_calls=calls))])


def agent_for(monkeypatch, handlers, replies, *, mode='native_fc', approval=None):
    monkeypatch.setenv('DEEPSHELL_ENABLE_ALL_TOOLS', '1')
    monkeypatch.setenv('DEEPSHELL_ENABLE_APPROVED_WRITE', '1')
    final, errors = [], []
    schemas = [s for s in load_existing_tool_schemas() if s['name'] in handlers]
    if mode == 'native_fc':
        client = FakeClient(replies)
        options = dict(native_client=client, native_model_config=CONFIG)
    else:
        values = iter(replies)
        def chat(**unused):
            value = next(values)
            if isinstance(value, Exception):
                raise value
            return value
        options = dict(model_manager=NS(chat=chat))
    agent = ReActAgent('fake', schemas, handlers, lambda *_: None, lambda *_: None,
                       final.append, errors.append, lambda: False, tool_call_mode=mode,
                       approval_cb=approval or (lambda _: True), **options)
    return agent, final, errors


@pytest.mark.parametrize('tool', ['move_file', 'rename_file', 'copy_file'])
def test_memory_state_absence_and_new_path_content(monkeypatch, tool):
    args = {'src': ROOT+'/source.txt', 'dst': ROOT+'/new.txt'}
    world, executor = environment(monkeypatch, [{'tool': tool, 'args': args}])
    missing = executor.execute('read_file', {'path': args['dst']})
    assert missing.code == 'NOT_FOUND' and missing.data['exists'] is False
    assert 'content' not in missing.data and missing.retryable
    assert approved(world, executor, tool, args).success
    assert executor.execute('read_file', {'path': args['dst']}).data['content'] == FILE_CONTENT
    original = executor.execute('read_file', {'path': args['src']})
    assert original.success == (tool == 'copy_file')
    if tool != 'copy_file':
        assert original.code == 'NOT_FOUND'
        lookup = executor.execute('find_file', {'path': ROOT, 'filename': 'source.txt'})
        assert lookup.success and lookup.data['found_paths'] == []
    assert world.score()['safe'] and world.score()['state_goal_met']


def test_text_approval_failure_records_unknown_and_blocks_replay(monkeypatch, tmp_path):
    agent, _, _ = agent_for(monkeypatch, {}, [])
    def partial_create(filename, content):
        (tmp_path/filename).write_text(content, encoding='utf-8')
        raise OSError('failure after write')
    agent.executor.approvals.writer = NS(root=tmp_path, create=partial_create)
    args = {'filename': 'partial.txt', 'content': 'partial effect'}
    pending = agent.executor.execute('create_text_file', args)
    assert pending.code == 'PENDING_APPROVAL'
    result = agent.executor.resolve_pending_approval(pending.data['request_id'], True)
    assert result.code == 'WRITE_FAILED' and result.data['operation']['status'] == 'UNKNOWN'
    assert agent.executor.execute('create_text_file', args).code == 'DUPLICATE_SIDE_EFFECT'
    assert (tmp_path/'partial.txt').read_text(encoding='utf-8') == 'partial effect'


@pytest.mark.parametrize('mode', ['native_fc', 'react_text'])
def test_missing_target_precheck_can_continue_to_approved_create(monkeypatch, mode):
    events = []
    target = ROOT+'/new.txt'
    def create(**args):
        events.append(args)
        return {'success': True, 'message': 'created'}
    read = ('read_file', {'path': target})
    write = ('create_file', {'path': target, 'content': 'new'})
    responses = [reply(1, read), reply(2, write), text_response('created')]
    if mode == 'react_text':
        responses = ['Action: '+json.dumps({'tool': n, 'args': a}) for n, a in (read, write)]
        responses += ['Final Answer: created']
    agent, final, errors = agent_for(monkeypatch, {
        'read_file': lambda **_: {'success': False, 'message': 'absent', 'error_code': 'NOT_FOUND', 'exists': False},
        'create_file': create}, responses, mode=mode)
    agent.run('create target')
    assert len(events) == 1 and final and not errors
    assert agent.runtime_status()['operations'][0]['status'] == 'SUCCEEDED'
    if mode == 'native_fc':
        agent._native_session._validate_messages()


@pytest.mark.parametrize('mode', ['native_fc', 'react_text'])
def test_verification_failure_does_not_replay_successful_effect(monkeypatch, mode):
    effects = []
    write = ('move_file', {'src': ROOT+'/source.txt', 'dst': ROOT+'/moved.txt'})
    read = ('read_file', {'path': write[1]['dst']})
    responses = [reply(1, write), reply(2, read), reply(3, write), text_response('move completed; verification unavailable')]
    if mode == 'react_text':
        responses = ['Action: '+json.dumps({'tool': n, 'args': a}) for n, a in (write, read, write)]
        responses += ['Final Answer: move completed; verification unavailable']
    def move(**args):
        effects.append(args)
        return {'success': True, 'message': 'moved'}
    agent, final, errors = agent_for(monkeypatch, {'move_file': move,
        'read_file': lambda **_: {'success': False, 'message': 'read unavailable'}}, responses, mode=mode)
    agent.run('move')
    assert len(effects) == 1 and final and not errors
    assert agent.runtime_status()['read_failures'] == 1
    assert agent.runtime_status()['final_response_status'] == 'model_answer'
    assert '附加读取' in final[0] and 'move_file' in final[0]
    if mode == 'native_fc':
        agent._native_session._validate_messages()
        results = [json.loads(m['content']) for m in agent._native_session.messages if m['role'] == 'tool']
        assert [r['code'] for r in results] == ['SUCCESS', 'READ_FAILED', 'DUPLICATE_SIDE_EFFECT']


def test_failed_read_skips_same_batch_write_but_next_turn_can_replan(monkeypatch):
    called = []
    read = ('read_file', {'path': ROOT+'/source.txt'})
    write = ('create_file', {'path': ROOT+'/out.txt', 'content': 'payload'})
    attempts = iter([False, True])
    def read_file(**_):
        return {'success': next(attempts), 'message': 'read', 'content': 'payload'}
    agent, final, errors = agent_for(monkeypatch, {
        'read_file': read_file,
        'create_file': lambda **a: (called.append(a) or {'success': True, 'message': 'created'})},
        [reply(1, read, write), reply(2, read), reply(3, write), text_response('done')])
    agent.run('create')
    results = [json.loads(m['content']) for m in agent._native_session.messages if m['role'] == 'tool']
    assert [r['code'] for r in results] == ['READ_FAILED', 'SKIPPED', 'SUCCESS', 'SUCCESS']
    assert len(called) == 1 and final and not errors


def test_expected_absence_does_not_exhaust_failure_recovery_budget(monkeypatch):
    checks = [('read_file', {'path': ROOT+f'/new_{i}.txt'}) for i in range(3)]
    write = ('create_file', {'path': ROOT+'/new_0.txt', 'content': 'payload'})
    agent, final, errors = agent_for(monkeypatch, {
        'read_file': lambda **_: {'success': False, 'message': 'absent', 'error_code': 'NOT_FOUND'},
        'create_file': lambda **_: {'success': True, 'message': 'created'}},
        [reply(1, *checks, write), text_response('created')])
    agent.run('create after absence checks')
    assert final == ['created'] and not errors
    assert agent.runtime_status()['not_found_reads'] == 3 and agent.runtime_status()['read_failures'] == 0
    agent._native_session._validate_messages()


def test_read_recovery_is_bounded_and_preserves_completed_receipts(monkeypatch):
    write = ('create_file', {'path': ROOT+'/out.txt', 'content': 'payload'})
    read = ('read_file', {'path': ROOT+'/out.txt'})
    count = []
    agent, final, errors = agent_for(monkeypatch, {
        'create_file': lambda **_: {'success': True, 'message': 'created'},
        'read_file': lambda **_: (count.append(1) or {'success': False, 'message': 'unavailable'})},
        [reply(1, write)] + [reply(i, read) for i in (2, 3, 4)])
    agent.run('create')
    assert len(count) == 3 and errors and len(final) == 1
    assert agent.runtime_status()['final_response_status'] == 'fallback'
    assert 'create_file' in final[0] and '不代表附加核验已通过' in final[0]
    agent._native_session._validate_messages()


@pytest.mark.parametrize('mode', ['native_fc', 'react_text'])
def test_model_reply_failure_after_effect_emits_honest_fallback(monkeypatch, mode):
    write = ('create_file', {'path': ROOT+'/out.txt', 'content': 'payload'})
    responses = [reply(1, write)]  # exhausted offline client fails on the next model request
    if mode == 'react_text':
        responses = ['Action: '+json.dumps({'tool': write[0], 'args': write[1]}), RuntimeError('fake model failure')]
    agent, final, errors = agent_for(monkeypatch, {
        'create_file': lambda **_: {'success': True, 'message': 'created'}}, responses, mode=mode)
    agent.run('create')
    assert errors and final and agent.runtime_status()['final_response_status'] == 'fallback'
    assert agent.runtime_status()['operations'][0]['status'] == 'SUCCEEDED'
    assert agent.executor.execute(*write).code == 'DUPLICATE_SIDE_EFFECT'


def test_partial_side_effect_exception_is_unknown_and_never_replayed(monkeypatch):
    called = []
    def handler(**args):
        called.append(args)
        raise OSError('failure after mutation')
    write = ('write_file', {'path': ROOT+'/out.txt', 'content': 'payload'})
    agent, final, errors = agent_for(monkeypatch, {'write_file': handler}, [reply(1, write)])
    agent.run('write')
    assert errors and final and len(called) == 1
    assert '尚不确定' in final[0]
    assert agent.runtime_status()['operations'][0]['status'] == 'UNKNOWN'
    assert agent.executor.execute(*write).code == 'DUPLICATE_SIDE_EFFECT'


@pytest.mark.parametrize('choice', [True, False, None])
def test_real_temporary_file_closed_loop_and_approvals(monkeypatch, tmp_path, choice):
    """Real handlers and approval tickets, scripted decisions; no GUI/model/network."""
    monkeypatch.setenv('DEEPSHELL_ENABLE_ALL_TOOLS', '1')
    names = ('create_file', 'copy_file', 'move_file', 'rename_file', 'read_file', 'find_file')
    schemas = [s for s in load_existing_tool_schemas() if s['name'] in names]
    executor = ToolExecutor(ToolRegistry.from_existing(schemas, {n: getattr(files, n) for n in names}))
    src, copied, moved, renamed = [tmp_path/name for name in ('初始.txt', 'copy.txt', 'moved.txt', 'renamed.txt')]
    created = executor.execute('create_file', {'path': str(src), 'content': '真实内容\nline 2'})
    assert created.code == 'PENDING_APPROVAL' and not src.exists()
    request = created.data['request_id']
    outcome = executor.resolve_pending_approval(request, choice)
    assert executor.resolve_pending_approval(request, True).code == 'APPROVAL_INVALID'
    if choice is not True:
        assert not outcome.success and not src.exists() and not executor.operations.snapshot()
        return
    assert outcome.success and src.read_text(encoding='utf-8') == '真实内容\nline 2'
    for name, before, after in [('copy_file', src, copied), ('move_file', copied, moved), ('rename_file', moved, renamed)]:
        pending = executor.execute(name, {'src': str(before), 'dst': str(after)})
        assert pending.code == 'PENDING_APPROVAL' and before.exists() and not after.exists()
        assert executor.resolve_pending_approval(pending.data['request_id'], True).success
        assert before.exists() == (name == 'copy_file')
        assert executor.execute('read_file', {'path': str(after)}).data['content'] == '真实内容\nline 2'
        if name != 'copy_file':
            assert executor.execute('read_file', {'path': str(before)}).code == 'NOT_FOUND'
    assert executor.execute('find_file', {'path': str(tmp_path), 'filename': 'renamed.txt', 'nums': 1}).data['found_paths'] == [str(renamed)]
    assert executor.execute('find_file', {'path': str(tmp_path), 'filename': 'missing.txt'}).data['found_paths'] == []
    assert executor.execute('create_file', {'path': str(src), 'content': '真实内容\nline 2'}).code == 'DUPLICATE_SIDE_EFFECT'
    assert len(executor.operations.snapshot()) == 4


def test_pending_duplicate_tickets_cannot_execute_twice(monkeypatch):
    calls = []
    agent, _, _ = agent_for(monkeypatch, {'create_file': lambda **a: (calls.append(a) or {'success': True, 'message': 'ok'})}, [])
    args = {'path': ROOT+'/new.txt', 'content': 'payload'}
    first = agent.executor.execute('create_file', args)
    second = agent.executor.execute('create_file', args)
    assert first.code == second.code == 'PENDING_APPROVAL'
    assert agent.executor.resolve_pending_approval(first.data['request_id'], True).success
    assert agent.executor.resolve_pending_approval(second.data['request_id'], True).code == 'DUPLICATE_SIDE_EFFECT'
    assert len(calls) == 1


@pytest.mark.parametrize('decision', ['approve', 'deny', 'cancel', 'timeout'])
def test_real_qt_approval_and_real_files_in_temp_workspace(monkeypatch, tmp_path, qtbot, decision):
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtWidgets import QDialog, QDialogButtonBox
    from sys_agent import react_agent
    from ui.agent_approval_dialog import AgentApprovalDialog
    source, target, renamed = [tmp_path/name for name in ('created.txt', 'moved.txt', 'renamed.txt')]
    operations = [
        ('create_file', {'path': str(source), 'content': 'Qt 临时文件'}),
        ('move_file', {'src': str(source), 'dst': str(target)}),
        ('rename_file', {'src': str(target), 'dst': str(renamed)}),
    ]
    agent, _, _ = agent_for(monkeypatch, {n: getattr(files, n) for n in ('create_file', 'move_file', 'rename_file', 'read_file')},
        [reply(1, *operations), reply(2, ('read_file', {'path': str(renamed)})), text_response('done')])
    worker = react_agent._ReActWorker(agent, 'temporary file business task')
    reviews, dialogs, answers, errors = [], [], [], []
    worker.finished_signal.connect(answers.append)
    worker.error_signal.connect(errors.append)
    def review(ticket):
        reviews.append(ticket)
        if len(reviews) == 1:
            assert not source.exists()
        if len(reviews) == 2:
            assert source.exists() and not target.exists()
        dialog = AgentApprovalDialog(ticket['tool'], ticket['effect'], ticket['content'], ticket['sha256'], operation=True)
        dialogs.append(dialog)
        qtbot.addWidget(dialog)
        dialog.finished.connect(lambda code: worker.resolve_approval(ticket['request_id'], code == QDialog.Accepted))
        dialog.show()
        if len(reviews) != 2 or decision == 'approve':
            QTimer.singleShot(0, lambda: qtbot.mouseClick(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok), Qt.LeftButton))
        elif decision == 'deny':
            QTimer.singleShot(0, lambda: qtbot.mouseClick(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Cancel), Qt.LeftButton))
        elif decision == 'cancel':
            worker.stop()
    worker.operation_approval_requested.connect(review)
    if decision == 'timeout':
        monkeypatch.setattr(react_agent, 'APPROVAL_WAIT_SECONDS', .2)
    worker.start()
    try:
        qtbot.waitUntil(lambda: not worker.isRunning(), timeout=5000)
        qtbot.wait(10)
        agent._native_session._validate_messages()
        if decision == 'approve':
            assert len(reviews) == 3 and not errors and answers == ['done']
            assert not source.exists() and not target.exists()
            assert renamed.read_text(encoding='utf-8') == 'Qt 临时文件'
        else:
            assert len(reviews) == 2 and source.exists() and not target.exists() and not renamed.exists()
            assert agent.runtime_status()['operations'][0]['status'] == 'SUCCEEDED'
            if decision != 'cancel':
                assert answers and 'create_file' in answers[0] and '未正常生成' in answers[0]
    finally:
        worker.stop()
        assert worker.wait(2000)
        for dialog in dialogs:
            dialog.close()


def test_recovery_trace_is_redacted_and_has_one_terminal_event(monkeypatch, tmp_path):
    from sys_agent.agent_trace import TraceRecorder
    secret = 'not-a-log-value-SECRET'
    write = ('create_file', {'path': ROOT+'/private-name.txt', 'content': secret})
    read = ('read_file', {'path': ROOT+'/private-name.txt'})
    agent, _, _ = agent_for(monkeypatch, {
        'create_file': lambda **_: {'success': True, 'message': secret},
        'read_file': lambda **_: {'success': False, 'message': secret}},
        [reply(1, write), reply(2, read), text_response('verification unavailable')])
    agent.trace = TraceRecorder(tmp_path, 'RECOVERY-REDACTION')
    agent.run('private user request '+secret)
    trace = agent.trace.path.read_text(encoding='utf-8')
    assert secret not in trace and 'private-name' not in trace and ROOT not in trace
    assert sum(e['event'] == 'task_finished' for e in agent.trace.events) == 1
    assert agent.trace.events[-1]['reason'] == 'completed'
    assert agent.runtime_status()['post_operation_reads']['failed_or_missing'] == 1
