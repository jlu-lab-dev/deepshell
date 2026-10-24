"""Opt-in real Qwen + real Qt signals/dialogs. OS handlers remain synthetic.

DEEPSHELL_TEST_LIVE_QWEN=1 enables network calls. Only approval of create_text_file
writes a generated file inside pytest's temporary workspace; no system tool runs.
"""
import ast
import json
import os
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.environ.get('DEEPSHELL_TEST_LIVE_QWEN') != '1', reason='Live Qwen test is opt-in')
LIVE_RUN_ID = time.time_ns()


@pytest.mark.parametrize('case', ['query', 'approve', 'deny', 'cancel'])
def test_real_qwen_native_fc_through_qt(monkeypatch, tmp_path, qtbot, case):
    from PyQt5.QtCore import Qt, QThread, QMetaObject, Q_ARG
    from PyQt5.QtWidgets import QWidget, QPlainTextEdit, QDialogButtonBox
    from sys_agent import react_agent
    from sys_agent.agent_trace import TraceRecorder
    from evals.agent_eval import load_existing_tool_schemas
    from sys_agent.native_fc_session import NativeFCSession
    from sys_agent.tool_policy import ALL_TOOL_NAMES

    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv('DEEPSHELL_ENABLE_ALL_TOOLS', '1')
    monkeypatch.setenv('DEEPSHELL_ENABLE_APPROVED_WRITE', '1')
    monkeypatch.setenv('DEEPSHELL_AGENT_WORKSPACE', str(tmp_path/'workspace'))
    monkeypatch.setitem(react_agent.ConfigManager().app_config['agent'], 'tool_call_mode', 'native_fc')
    calls, returned_tools, final, errors = [], [], [], []
    trace = TraceRecorder(tmp_path/'traces')
    def handler(name):
        def invoke(**args):
            calls.append({'tool': name, 'args': args})
            return {'success': True, 'message': '合成工具结果', 'path': r'D:\NativeFCEvalWorkspace'}
        return invoke
    handlers = {name: handler(name) for name in ALL_TOOL_NAMES}
    schemas = load_existing_tool_schemas()
    monkeypatch.setattr(react_agent.ReActAgentController, '_load_all_tools', lambda self: (schemas, handlers))
    original_agent = react_agent.ReActAgent
    def factory(**kwargs):
        kwargs['trace_recorder'] = trace
        return original_agent(**kwargs)
    monkeypatch.setattr(react_agent, 'ReActAgent', factory)
    original_result = NativeFCSession.add_tool_result
    def record_result(session, result, call_id=None):
        original_result(session, result, call_id)
        tool = session.messages[-1]
        assistant = session.messages[-2]
        assert tool['role'] == 'tool'
        assert tool['tool_call_id'] == assistant['tool_calls'][0]['id']
        returned_tools.append({'tool': result['tool'], 'code': result['code'],
                               'tool_call_id_matched': True})
    monkeypatch.setattr(NativeFCSession, 'add_tool_result', record_result)

    controller = react_agent.ReActAgentController('Qwen-FLASH')
    thread = QThread()
    controller.moveToThread(thread)
    thread.finished.connect(controller.deleteLater)
    tree = ast.parse((root/'main_window.py').read_text(encoding='utf-8'))
    main = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'MainWin')
    names = {'handle_agent_approval_requested', 'handle_agent_operation_approval_requested',
             'handle_agent_approval_closed', 'cancel_agent_approvals'}
    namespace = {}
    exec(compile(ast.Module(body=[node for node in main.body if isinstance(node, ast.FunctionDef) and node.name in names],
                            type_ignores=[]), 'main_window.py', 'exec'), namespace)
    Host = type('NativeApprovalHost', (QWidget,), {name: namespace[name] for name in names})
    host = Host()
    qtbot.addWidget(host)
    host._agent_approval_dialogs = {}
    host.agent_controller = controller
    controller.approval_requested.connect(host.handle_agent_approval_requested)
    controller.operation_approval_requested.connect(host.handle_agent_operation_approval_requested)
    controller.approval_closed.connect(host.handle_agent_approval_closed)
    controller.finished_signal.connect(final.append)
    controller.error_signal.connect(errors.append)
    question = ('查询当前工作目录。' if case == 'query' else
                '使用 Agent 专用工作区文本创建功能创建 hello_fc.txt，内容精确为 Hello FC，不使用普通路径创建工具。')
    thread.start()
    QMetaObject.invokeMethod(controller, 'start_workflow', Qt.QueuedConnection, Q_ARG(str, question), Q_ARG(list, []))
    try:
        if case != 'query':
            qtbot.waitUntil(lambda: bool(host._agent_approval_dialogs) or bool(errors) or bool(final), timeout=90000)
            assert host._agent_approval_dialogs, errors or final
            _, dialog = next(iter(host._agent_approval_dialogs.items()))
            assert not (tmp_path/'workspace').exists()
            assert not calls
            preview = dialog.findChild(QPlainTextEdit)
            assert preview.isReadOnly() and preview.toPlainText() == 'Hello FC'
            if case == 'cancel':
                host.cancel_agent_approvals()
            else:
                buttons = dialog.findChild(QDialogButtonBox)
                qtbot.mouseClick(buttons.button(QDialogButtonBox.Ok if case == 'approve' else QDialogButtonBox.Cancel), Qt.LeftButton)
        if case != 'cancel': qtbot.waitUntil(lambda: bool(final) or bool(errors), timeout=90000)
        qtbot.waitUntil(lambda: controller._worker is not None and not controller._worker.isRunning(), timeout=10000)
        assert not errors
        if case == 'cancel':
            assert not final and trace.events[-1]['reason'] == 'cancelled'
        else:
            assert final[-1].strip()
        if case == 'query':
            assert [call['tool'] for call in calls] == ['get_current_directory']
            assert r'D:\NativeFCEvalWorkspace' in final[-1]
        elif case == 'approve':
            assert (tmp_path/'workspace/hello_fc.txt').read_text(encoding='utf-8') == 'Hello FC'
            assert not calls
        else:
            assert not (tmp_path/'workspace/hello_fc.txt').exists() and not calls
        assert not host._agent_approval_dialogs
        assert len(returned_tools) == 1
        assert 'Hello FC' not in trace.path.read_text(encoding='utf-8')
        output = root/'logs/native_fc_validation'/f'reliability_qt_{LIVE_RUN_ID}'
        output.mkdir(parents=True, exist_ok=True)
        (output/f'live_qt_{case}.json').write_text(json.dumps({'case': case, 'passed': True,
            'model_id': react_agent.ConfigManager().get_model_config('Qwen-FLASH')['model_name'],
            'trace_events': trace.events, 'tool_results_returned': returned_tools,
            'approval_ui': case != 'query', 'physical_file_created': case == 'approve',
            'gui_click': 'automated' if case != 'query' else None}, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        controller.cancel_pending_approval()
        if controller._worker is not None:
            assert controller._worker.wait(65000)
        thread.quit()
        assert thread.wait(1000)
