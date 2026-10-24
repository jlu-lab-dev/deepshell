"""故障注入验证分类、预算、取消与副作用边界；不联网。"""
import json
from copy import deepcopy
from types import SimpleNamespace as NS

import httpx
import openai
import pytest

from sys_agent.native_fc_session import (
    NativeFCSession, NativeFCProtocolError, RequestPolicy,
    ModelBudgetExceeded, ModelRequestCancelled, classify_model_error,
)
from test_native_fc_session import CONFIG, SCHEMA, tool_response, text_response


class Clock:
    def __init__(self): self.now = 0.0
    def __call__(self): return self.now
    def sleep(self, seconds): self.now += seconds


class Client:
    def __init__(self, replies):
        self.replies, self.requests = iter(replies), []
        self.chat = NS(completions=NS(create=self.create))
    def create(self, **kwargs):
        self.requests.append(deepcopy(kwargs))
        reply = next(self.replies)
        if callable(reply): reply = reply()
        if isinstance(reply, Exception): raise reply
        return reply


def session(replies, **kwargs):
    clock, client = Clock(), Client(replies)
    s = NativeFCSession(CONFIG, SCHEMA, history=[], user_input='private input',
        permission_text='read only', client=client, clock=clock, sleep=clock.sleep, **kwargs)
    return s, client, clock


def http_error(status, **headers):
    response = httpx.Response(status, request=httpx.Request('POST', 'https://example.invalid/v1'),
                              headers={'x-request-id': 'req_test', **headers})
    cls = openai.RateLimitError if status == 429 else openai.APIStatusError
    return cls('private server error body', response=response, body={'private': 'not for trace'})


@pytest.mark.parametrize('status', [400, 401, 403, 404, 422])
def test_permanent_http_errors_are_not_retried(status):
    s, client, _ = session([http_error(status), text_response()])
    with pytest.raises(openai.APIStatusError): s.next_react_text()
    assert len(client.requests) == 1
    assert s.request_events[0]['http_status'] == status
    assert s.request_events[0]['request_id'] == 'req_test'
    assert not s.request_events[0]['retry_scheduled']
    assert 'private' not in json.dumps(s.request_events)


@pytest.mark.parametrize('status', [408, 409, 429, 500, 503])
def test_transient_http_retries_once_without_mutating_context(status):
    s, client, clock = session([http_error(status, **{'retry-after': '0.2'}), tool_response()])
    s.next_react_text()
    assert len(client.requests) == 2 and clock() == pytest.approx(.2)
    assert s.request_events[0]['retry_scheduled']
    assert [e['success'] for e in s.request_events] == [False, True]
    assert sum(m['role'] == 'assistant' for m in s.messages) == 1


@pytest.mark.parametrize('header', [{'retry-after': '99'}, {'x-should-retry': 'false'}])
def test_never_ignores_server_delay_or_no_retry(header):
    s, client, clock = session([http_error(429, **header), text_response()], policy=RequestPolicy(task_budget=5))
    with pytest.raises(openai.RateLimitError): s.next_react_text()
    assert len(client.requests) == 1 and clock() == 0


@pytest.mark.parametrize('phase,kind', [('connect',httpx.ConnectTimeout), ('read',httpx.ReadTimeout),
                                     ('write',httpx.WriteTimeout), ('pool',httpx.PoolTimeout)])
def test_timeout_phase_classification(phase, kind):
    error = openai.APITimeoutError(request=httpx.Request('POST', 'https://example.invalid'))
    error.__cause__ = kind('private cause')
    s, client, _ = session([error, text_response('ok')])
    s.next_react_text()
    assert len(client.requests) == 2
    assert s.request_events[0]['error_kind'] == 'timeout'
    assert s.request_events[0]['timeout_phase'] == phase


def test_connection_failure_is_bounded_and_observed():
    error = openai.APIConnectionError(request=httpx.Request('POST', 'https://example.invalid'))
    s, client, _ = session([error, error, text_response()])
    with pytest.raises(openai.APIConnectionError): s.next_react_text()
    assert len(client.requests) == 2
    assert all(e['error_kind'] == 'connection' for e in s.request_events)


def test_expired_budget_sends_no_request():
    s, client, clock = session([tool_response()], policy=RequestPolicy(task_budget=1))
    clock.now = 2
    with pytest.raises(ModelBudgetExceeded): s.next_react_text()
    assert not client.requests


def test_reply_after_deadline_cannot_become_tool_action():
    s, client, clock = session([], policy=RequestPolicy(task_budget=1))
    def late():
        clock.now = 2
        return tool_response()
    client.replies = iter([late])
    with pytest.raises(ModelBudgetExceeded): s.next_react_text()
    assert s.last_action is None and s._pending_call_id is None


def test_cancellation_before_request_and_during_backoff():
    cancelled = [True]
    s, client, _ = session([http_error(503), tool_response()], stop_flag=lambda: cancelled[0])
    with pytest.raises(ModelRequestCancelled): s.next_react_text()
    assert not client.requests
    cancelled[0] = False
    original = s._sleep
    def sleep(seconds):
        original(seconds)
        cancelled[0] = True
    s._sleep = sleep
    with pytest.raises(ModelRequestCancelled): s.next_react_text()
    assert len(client.requests) == 1


@pytest.mark.parametrize('args', ['{"x":1e999}', '{"x":{"n":-1e999}}'])
def test_overflow_cannot_mutate_pending_state(args):
    s, _, _ = session([tool_response(arguments=args)])
    with pytest.raises(NativeFCProtocolError): s.next_react_text()
    assert s.last_action is None and not s._pending_call_id
    assert len(s.messages) == 2


def test_orphan_history_rejected_before_network():
    s, client, _ = session([tool_response()])
    s.messages.append({'role': 'tool', 'tool_call_id': 'orphan', 'content': 'private'})
    with pytest.raises(NativeFCProtocolError): s.next_react_text()
    assert not client.requests


@pytest.mark.parametrize('finish', ['length', 'content_filter'])
def test_truncated_calls_do_not_execute_or_retry(finish):
    reply = tool_response()
    reply.choices[0].finish_reason = finish
    s, client, _ = session([reply, tool_response()])
    with pytest.raises(NativeFCProtocolError): s.next_react_text()
    assert len(client.requests) == 1 and s.last_action is None


def test_followup_request_retry_never_reexecutes_approved_handler(monkeypatch):
    from sys_agent import react_agent
    monkeypatch.setenv('DEEPSHELL_ENABLE_ALL_TOOLS', '1')
    monkeypatch.setenv('DEEPSHELL_ENABLE_APPROVED_WRITE', '1')
    client = Client([tool_response(name='run_program', arguments='{"command":"fake"}'),
                     http_error(503, **{'retry-after': '0'}), text_response('done')])
    calls, approvals, final, errors = [], [], [], []
    schema = {'name':'run_program', 'parameters':{'type':'object', 'properties':{'command':{'type':'string'}}, 'required':['command']}}
    def handler(**args):
        assert approvals
        calls.append(args)
        return {'success':True, 'message':'mock execution'}
    agent = react_agent.ReActAgent('fake', [schema], {'run_program':handler}, lambda *_:None, lambda *_:None,
        final.append, errors.append, lambda:False, tool_call_mode='native_fc', native_client=client,
        native_model_config=CONFIG, approval_cb=lambda review:(approvals.append(review) or True))
    agent.run('synthetic request')
    assert not errors and final == ['done']
    assert len(calls) == len(approvals) == 1 and len(client.requests) == 3
    assert client.requests[-1]['messages'][-1]['role'] == 'tool'


def test_stateless_text_context_not_duplicated_or_written_to_memory():
    from chat.model_manager import ModelManager
    cls = ModelManager.__wrapped__
    manager = object.__new__(cls)
    manager.memory = {}
    requests = []
    def stream(messages):
        requests.append(messages)
        return [NS(content='reply')]
    manager.get_model = lambda _: NS(stream=stream)
    manager.chat_once('fake', ['question'], 'system', 'session')
    manager.chat_once('fake', ['question','action','observation'], 'system', 'session')
    assert [len(r) for r in requests] == [2,4]
    assert requests[-1][0].type == 'system' and manager.memory == {}


def test_network_metadata_allowlist_does_not_persist_body_or_bad_request_id(tmp_path):
    from sys_agent.agent_trace import TraceRecorder
    trace = TraceRecorder(tmp_path)
    trace.record('model_request', request_id='private/path\nsecret', error_type='private message',
                 error_kind='timeout', request_bytes=123, http_status=503, attempt=1)
    raw = trace.path.read_text(encoding='utf-8')
    assert 'private' not in raw and 'secret' not in raw
    with pytest.raises(TypeError): trace.record('model_request', body='private')


def test_protocol_history_grows_linearly_with_paired_results():
    s, client, _ = session([tool_response(id='first'), tool_response(id='second'), text_response('done')])
    s.next_react_text()
    s.add_tool_result({'success':True,'code':'SUCCESS'})
    s.next_react_text()
    s.add_tool_result({'success':True,'code':'SUCCESS'})
    s.next_react_text()
    assert [len(r['messages']) for r in client.requests] == [2,4,6]
    for request in client.requests[1:]:
        assert request['messages'][-1]['tool_call_id'] == request['messages'][-2]['tool_calls'][0]['id']


def test_repeat_call_id_rejected_without_new_pending():
    s, client, _ = session([tool_response(id='same'),tool_response(id='same')])
    s.next_react_text()
    s.add_tool_result({'success':True})
    with pytest.raises(NativeFCProtocolError): s.next_react_text()
    assert s._pending_call_id is None and len(s.messages) == 4


@pytest.mark.parametrize('policy', [dict(request_timeout=0),dict(task_budget=float('inf')),
                                  dict(max_retries=4),dict(max_retries=True),dict(backoff_base=-1)])
def test_invalid_network_policy_is_local_error(policy):
    with pytest.raises(ValueError): RequestPolicy(**policy)


def test_stability_metrics_keep_api_decisions_and_all_tasks_separate():
    from evals.native_fc_stability import summarize
    good=dict(category='safe_tool',decision_observed=True,selected_expected_tool=True,rule_pass=True,
              api_attempts=2,api_successes=2,retries=0,elapsed_ms=10,model_errors=[])
    failed=dict(category='safe_tool',decision_observed=False,selected_expected_tool=False,rule_pass=False,
                api_attempts=1,api_successes=0,retries=0,elapsed_ms=20,model_errors=['timeout'])
    result=summarize([good,failed])
    assert result['api_success_rate'] == 2/3
    assert result['observed_tool_selection_rate'] == 1
    assert result['end_to_end_rule_rate'] == .5
    assert result['classified_errors'] == {'timeout':1}


@pytest.mark.parametrize('compact', [True,False])
def test_history_uses_compact_memory_once_and_keeps_legacy_workflows(monkeypatch, compact):
    from chat import memory_compressor
    from chat.message_helpers import make_agent_workflow_message, make_agent_memory_message
    from sys_agent.react_agent import ReActAgentController
    monkeypatch.setattr(memory_compressor,'MemoryCompressor',lambda:NS(compress_agent_history=lambda history:history))
    workflow=make_agent_workflow_message('assistant','react','unique final',[
        {'action':{'tool':'get_current_directory'},'observation':'observed','success':True}])
    messages=[NS(role='assistant',content=workflow)]
    if compact:
        messages.append(NS(role='assistant',content=make_agent_memory_message([
            {'tool':'get_current_directory','result_summary':'observed'}],'unique final')))
    controller=NS()
    ReActAgentController.load_history(controller,NS(get_messages=lambda _:messages),'history')
    assert sum('unique final' in entry for entry in controller._history) == 1
    assert sum('observed' in entry for entry in controller._history) == 1


def test_invalid_required_schema_is_rejected_before_client_creation():
    bad=[{'name':'broken','parameters':{'type':'object','properties':{},'required':['missing']}}]
    with pytest.raises(ValueError):
        NativeFCSession(CONFIG,bad,history=[],user_input='',permission_text='')


def test_injected_sdk_cannot_add_hidden_retries():
    with openai.OpenAI(api_key='fake',base_url='https://example.invalid',max_retries=2) as client:
        with pytest.raises(ValueError,match='max_retries=0'):
            NativeFCSession(CONFIG,SCHEMA,history=[],user_input='',permission_text='',client=client)


def test_tool_exception_does_not_restart_agent_or_retry_handler(monkeypatch):
    from sys_agent.react_agent import ReActAgent
    calls,errors=[],[]
    def handler():
        calls.append('invoked')
        raise RuntimeError('unknown tool outcome')
    client=Client([tool_response(), text_response('must not be requested')])
    agent=ReActAgent('fake',SCHEMA,{'get_current_directory':handler},lambda *_:None,lambda *_:None,
        lambda *_:None,errors.append,lambda:False,tool_call_mode='native_fc',native_client=client,native_model_config=CONFIG)
    agent.run('query')
    assert errors and len(calls)==1 and len(client.requests)==1


def test_final_bubble_persistence_and_qt_history_replay(monkeypatch, qtbot):
    import ast, logging
    from pathlib import Path
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QLabel
    from chat import message_helpers as helpers, memory_compressor
    from sys_agent.react_agent import ReActAgentController
    from ui.chat.bubble_message import AgentHistoryWidget
    chain=[{'iteration':1,'thought':'visible step','action':{'tool':'get_current_directory','args':{}},
            'observation':'query succeeded','success':True}]
    records,bubbles,buttons=[],[],[]
    repo=NS(add_message=lambda sid,role,content:records.append(NS(role=role,content=content)),
            update_timestamp=lambda _:None,get_messages=lambda _:records)
    host=NS(show_waiting_message=lambda _:None,add_bubble_message=lambda text,**_:bubbles.append(text),
        input_field=NS(set_send_button_status=buttons.append),conversation_repo=repo,
        sendTask=NS(assistant=NS(session_id='history')),current_workflow_container='workflow',
        agent_controller=NS(_thought_chain=chain,_tool_results=[{'tool':'get_current_directory','result_summary':'query succeeded'}]))
    tree=ast.parse((Path(__file__).resolve().parents[1]/'main_window.py').read_text(encoding='utf-8'))
    main=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='MainWin')
    method=next(n for n in main.body if isinstance(n,ast.FunctionDef) and n.name=='handle_agent_finished')
    scope={'logging':logging,'make_agent_workflow_message':helpers.make_agent_workflow_message,
           'make_agent_memory_message':helpers.make_agent_memory_message}
    exec(compile(ast.Module(body=[method],type_ignores=[]),'main_window.py','exec'),scope)
    scope['handle_agent_finished'](host,'final roundtrip')
    assert bubbles==['final roundtrip'] and buttons[-1] is True and host.current_workflow_container is None
    assert [helpers.parse_message_content(r.content)['type'] for r in records]==['agent_workflow','agent_memory']
    restored=helpers.parse_message_content(records[0].content)
    widget=AgentHistoryWidget(restored['final_result'],restored['mode'],restored['thought_chain'])
    qtbot.addWidget(widget)
    widget.show()
    assert sum(label.text()=='final roundtrip' for label in widget.findChildren(QLabel))==1
    qtbot.mouseClick(widget._toggle_btn,Qt.LeftButton)
    assert widget._expanded and widget._steps_container.isVisible()
    monkeypatch.setattr(memory_compressor,'MemoryCompressor',lambda:NS(compress_agent_history=lambda h:h))
    controller=NS()
    ReActAgentController.load_history(controller,repo,'history')
    assert sum('final roundtrip' in text for text in controller._history)==1
