"""Day4 受审批工具与既有 Registry/Executor 的联动测试。"""
from pathlib import Path

import pytest
from sys_agent.tool_registry import ToolRegistry
from sys_agent.tool_executor import ToolExecutor


def make_executor(monkeypatch, tmp_path):
    monkeypatch.setenv('DEEPSHELL_ENABLE_APPROVED_WRITE', '1')
    monkeypatch.setenv('DEEPSHELL_AGENT_WORKSPACE', str(tmp_path / 'workspace'))
    registry = ToolRegistry.from_existing([], {})
    return ToolExecutor(registry)


def test_write_tool_opt_in(monkeypatch):
    monkeypatch.delenv('DEEPSHELL_ENABLE_APPROVED_WRITE', raising=False)
    registry = ToolRegistry.from_existing([], {})
    assert 'create_text_file' not in [t['name'] for t in registry.get_tool_schemas()]


def test_write_only_after_approval(monkeypatch, tmp_path):
    exe = make_executor(monkeypatch, tmp_path)
    expected = tmp_path / 'workspace' / 'hello.txt'
    pending = exe.execute('create_text_file', {'filename':'hello.txt','content':'Hello DeepShell'})
    assert pending.code == 'PENDING_APPROVAL'
    assert not expected.exists()
    request_id = pending.data['request_id']
    review = exe.get_pending_approval(request_id)
    assert review['content'] == 'Hello DeepShell'
    completed = exe.resolve_pending_approval(request_id, True)
    assert completed.success
    assert expected.read_text(encoding='utf-8') == 'Hello DeepShell'
    assert exe.resolve_pending_approval(request_id, True).code == 'APPROVAL_INVALID'


def test_write_denied_and_bad_path(monkeypatch, tmp_path):
    exe = make_executor(monkeypatch, tmp_path)
    bad = exe.execute('create_text_file', {'filename':'../escape.txt','content':'unsafe'})
    assert bad.code == 'INVALID_ARGS'
    pending = exe.execute('create_text_file', {'filename':'no.txt','content':'no'})
    assert exe.resolve_pending_approval(pending.data['request_id'], False).code == 'APPROVAL_DENIED'
    assert not (tmp_path / 'workspace' / 'no.txt').exists()


def test_original_write_file_still_forbidden(monkeypatch, tmp_path):
    exe = make_executor(monkeypatch, tmp_path)
    # 其他高危工具仍然不会被这个功能标志放行。
    result = exe.execute('write_file', {'path':'anything.txt','content':'oops'})
    assert result.code in ('UNKNOWN_TOOL', 'PERMISSION_DENIED')
    with pytest.raises(PermissionError):
        exe.registry.get_function_map()['create_text_file'](filename='x.txt', content='bypass')


@pytest.mark.parametrize('choice', ['approve', 'deny', 'close', 'timeout', 'stop'])
@pytest.mark.parametrize('tool_name', ['create_text_file', 'run_program'])
@pytest.mark.parametrize('protocol', ['react_text', 'native_fc'])
def test_real_qt_approval_loop(monkeypatch, tmp_path, qtbot, choice, tool_name, protocol):
    """真实 Qt 双线程及 MainWin 审批槽；模型使用脚本，写入只在 tmp_path。"""
    import ast
    import json
    from types import SimpleNamespace
    from unittest.mock import Mock
    from PyQt5.QtCore import Qt, QThread, QMetaObject, Q_ARG
    from PyQt5.QtWidgets import QWidget, QDialogButtonBox, QPlainTextEdit
    from sys_agent import react_agent
    from sys_agent.agent_trace import TraceRecorder

    monkeypatch.setenv('DEEPSHELL_ENABLE_APPROVED_WRITE', '1')
    monkeypatch.setenv('DEEPSHELL_ENABLE_ALL_TOOLS', '1')
    monkeypatch.setenv('DEEPSHELL_AGENT_WORKSPACE', str(tmp_path / 'workspace'))
    if choice == 'timeout':
        monkeypatch.setattr(react_agent, 'APPROVAL_WAIT_SECONDS', 0.5)
    body = 'PRIVATE_BODY_123'
    arguments = {'filename': 'hello.txt', 'content': body} if tool_name == 'create_text_file' else {'command': body}
    calls = []
    schemas = [{'name': 'run_program', 'parameters': {'type': 'object',
                'properties': {'command': {'type': 'string'}}, 'required': ['command']}}]
    def fake_command(**args):
        calls.append(args)
        return {'success': True, 'message': 'mock command completed'}
    model = SimpleNamespace(chat=Mock(side_effect=[
        'Thought: create file\nAction: ' + json.dumps({
            'tool': tool_name, 'args': arguments}),
        'Final Answer: created successfully',
    ]))
    trace = TraceRecorder(tmp_path / 'traces')
    def native_create(**kwargs):
        reply = model.chat()
        action = react_agent._extract_action(reply)
        message = SimpleNamespace(content=None, tool_calls=[SimpleNamespace(id='call_qt', type='function',
            function=SimpleNamespace(name=action['tool'], arguments=json.dumps(action['args'])))]) if action else SimpleNamespace(
            content=react_agent._extract_final_answer(reply), tool_calls=[])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])
    native_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=native_create)))
    monkeypatch.setattr(react_agent.ConfigManager(), 'get_model_config', lambda _: {
        'type': 'openai_compatible', 'api_base': 'https://example.invalid/v1', 'api_key': 'fake', 'model_name': 'fake'})
    monkeypatch.setitem(react_agent.ConfigManager().app_config['agent'], 'tool_call_mode', protocol)
    agent = react_agent.ReActAgent('fake', schemas, {'run_program': fake_command}, lambda *_: None, lambda *_: None,
        lambda *_: None, lambda *_: None, lambda: False, model_manager=model, trace_recorder=trace,
        tool_call_mode=protocol, native_client=native_client)
    def agent_factory(**kwargs):
        assert kwargs['tool_call_mode'] == protocol
        agent.thought_chain_collector = kwargs['thought_chain_collector']
        return agent
    monkeypatch.setattr(react_agent, 'ReActAgent', agent_factory)
    monkeypatch.setattr(react_agent.ReActAgentController, '_load_all_tools', lambda self: ([], {}))
    controller = react_agent.ReActAgentController('fake')
    thread = QThread()
    controller.moveToThread(thread)
    thread.finished.connect(controller.deleteLater)
    tree = ast.parse((Path(__file__).resolve().parents[1] / 'main_window.py').read_text(encoding='utf-8'))
    main = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'MainWin')
    names = {'handle_agent_approval_requested', 'handle_agent_operation_approval_requested',
             'handle_agent_approval_closed', 'cancel_agent_approvals'}
    ns = {}
    exec(compile(ast.Module(body=[node for node in main.body if isinstance(node, ast.FunctionDef)
                                and node.name in names], type_ignores=[]), 'main_window.py', 'exec'), ns)
    Host = type('ApprovalHost', (QWidget,), {name: ns[name] for name in names})
    host = Host()
    qtbot.addWidget(host)
    host._agent_approval_dialogs = {}
    host.agent_controller = controller
    controller.approval_requested.connect(host.handle_agent_approval_requested)
    controller.operation_approval_requested.connect(host.handle_agent_operation_approval_requested)
    controller.approval_closed.connect(host.handle_agent_approval_closed)
    final, errors = [], []
    controller.finished_signal.connect(final.append)
    controller.error_signal.connect(errors.append)
    thread.start()
    QMetaObject.invokeMethod(controller, 'start_workflow', Qt.QueuedConnection,
                             Q_ARG(str, 'create file'), Q_ARG(list, []))
    try:
        qtbot.waitUntil(lambda: bool(host._agent_approval_dialogs), timeout=3000)
        worker = controller._worker
        request_id, dialog = next(iter(host._agent_approval_dialogs.items()))
        assert not (tmp_path / 'workspace').exists()
        preview = dialog.findChild(QPlainTextEdit)
        assert preview.isReadOnly() and body in preview.toPlainText()
        assert not calls
        buttons = dialog.findChild(QDialogButtonBox)
        if choice == 'approve':
            worker.resolve_approval('wrong-request-id', True)
            assert not worker._approval_event.is_set()
            qtbot.mouseClick(buttons.button(QDialogButtonBox.Ok), Qt.LeftButton)
            worker.resolve_approval(request_id, False)
        elif choice == 'deny':
            qtbot.mouseClick(buttons.button(QDialogButtonBox.Cancel), Qt.LeftButton)
        elif choice == 'close':
            dialog.close()
        elif choice == 'stop':
            host.cancel_agent_approvals()
        qtbot.waitUntil(lambda: not worker.isRunning(), timeout=3000)
        qtbot.waitUntil(lambda: not host._agent_approval_dialogs, timeout=3000)
        assert not errors
        target = tmp_path / 'workspace' / 'hello.txt'
        if choice == 'approve':
            if tool_name == 'create_text_file':
                assert target.read_text(encoding='utf-8') == body and not calls
            else:
                assert calls == [{'command': body}] and not target.exists()
            assert model.chat.call_count == 2
            assert 'content' not in controller._tool_results[0]['args']
        else:
            assert not target.exists() and not calls
        if choice == 'timeout':
            assert any(event.get('code') == 'APPROVAL_TIMEOUT' for event in trace.events)
        if choice == 'stop':
            assert trace.events[-1]['reason'] == 'cancelled' and not final
        assert body not in trace.path.read_text(encoding='utf-8')
        assert body not in json.dumps(controller._thought_chain)
    finally:
        controller.cancel_pending_approval()
        if controller._worker is not None:
            assert controller._worker.wait(1000)
        thread.quit()
        assert thread.wait(1000)
