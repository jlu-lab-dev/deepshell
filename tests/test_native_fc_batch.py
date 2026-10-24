"""批次协议、安全预检查与顺序审批；全部 handler 为模拟实现。"""
import json
from types import SimpleNamespace as NS
import pytest
from test_native_fc_session import FakeClient,CONFIG,tool_response,text_response
from evals.agent_eval import load_existing_tool_schemas
from sys_agent.react_agent import ReActAgent
from sys_agent.native_fc_session import NativeFCSession,NativeFCProtocolError


def batch(items):
    calls=[]
    for i,(name,args) in enumerate(items):
        calls.append(NS(id=f'batch_{i}',type='function',function=NS(name=name,arguments=json.dumps(args))))
    return NS(choices=[NS(message=NS(content=None,tool_calls=calls))])


def run(monkeypatch,items,handlers,approval=None,stop=None):
    monkeypatch.setenv('DEEPSHELL_ENABLE_ALL_TOOLS','1')
    monkeypatch.setenv('DEEPSHELL_ENABLE_APPROVED_WRITE','1')
    client=FakeClient([batch(items),text_response('done')])
    final,errors,chain=[],[],[]
    agent=ReActAgent('fake',[s for s in load_existing_tool_schemas() if s['name'] in handlers],handlers,lambda *_:None,lambda *_:None,
        final.append,errors.append,stop or (lambda:False),thought_chain_collector=chain.append,
        tool_call_mode='native_fc',native_client=client,native_model_config=CONFIG,approval_cb=approval)
    agent.run('synthetic')
    session=agent._native_session
    session._validate_messages()
    tools=[m for m in session.messages if m['role']=='tool']
    assert len(tools)==len(items)
    assert [m['tool_call_id'] for m in tools]==[f'batch_{i}' for i in range(len(items))]
    return [json.loads(m['content']) for m in tools],final,errors,client


def test_two_readonly_and_whole_batch_precheck(monkeypatch):
    calls=[]
    handlers={n:lambda n=n,**args:(calls.append(n) or {'success':True,'message':'ok'}) for n in ('get_current_directory','list_running_applications')}
    results,final,errors,client=run(monkeypatch,[(n,{}) for n in handlers],handlers)
    assert calls==list(handlers) and all(r['success'] for r in results)
    assert final==['done'] and not errors
    assert [m['role'] for m in client.requests[-1]['messages']][-3:]==['assistant','tool','tool']


def test_invalid_parameter_does_not_lose_valid_result(monkeypatch):
    calls=[]
    handlers={'get_current_directory':lambda:(calls.append(1) or {'success':True,'message':'ok'}),
              'list_applications_by_memory_usage':lambda **_:pytest.fail('invalid handler executed')}
    results,final,errors,_=run(monkeypatch,[('get_current_directory',{}),('list_applications_by_memory_usage',{'memory_threshold_mb':'500'})],handlers)
    assert calls==[1] and [r['code'] for r in results]==['SUCCESS','INVALID_ARGS']
    assert final==['done']


@pytest.mark.parametrize('choice',[True,False,None])
def test_side_effects_need_each_approval_and_stop_after_denial(monkeypatch,choice):
    calls=[]; approvals=[]
    handlers={'run_program':lambda **a:(calls.append(a) or {'success':True,'message':'ok'})}
    def approve(review): approvals.append(review); return choice
    results,_,_,_=run(monkeypatch,[('run_program',{'command':'fake1'}),('run_program',{'command':'fake2'})],handlers,approve)
    assert len(approvals)==(2 if choice is True else 1)
    assert len(calls)==(2 if choice is True else 0)
    if choice is not True: assert results[-1]['code']=='SKIPPED'


def test_cancel_during_approval_blocks_all_remaining(monkeypatch):
    cancelled=[False]
    def approve(_): cancelled[0]=True; return True
    results,final,errors,_=run(monkeypatch,[('run_program',{'command':'fake'}),('shutdown_system',{})],
        {'run_program':lambda **_:pytest.fail('cancelled handler executed'),'shutdown_system':lambda:pytest.fail('shutdown executed')},
        approve,lambda:cancelled[0])
    assert all(r['code']=='CANCELLED' for r in results) and not final and not errors


def test_failure_allows_readonly_but_skips_later_writes(monkeypatch):
    calls=[]
    def fail(): raise RuntimeError('simulated')
    results,_,errors,_=run(monkeypatch,[('get_current_directory',{}),('list_running_applications',{}),('run_program',{'command':'fake'})],
        {'get_current_directory':fail,'list_running_applications':lambda:(calls.append('read') or {'success':True,'message':'ok'}),
         'run_program':lambda **_:pytest.fail('write after failure')},lambda _:True)
    assert [r['code'] for r in results]==['TOOL_ERROR','SUCCESS','SKIPPED'] and calls==['read'] and errors


@pytest.mark.parametrize('mode',['duplicate','too_many'])
def test_invalid_envelope_is_atomic(mode):
    reply=batch([('get_current_directory',{})]* (9 if mode=='too_many' else 2))
    if mode=='duplicate': reply.choices[0].message.tool_calls[1].id='batch_0'
    session=NativeFCSession(CONFIG,[],history=[],user_input='',permission_text='',client=FakeClient([reply]))
    with pytest.raises(NativeFCProtocolError):session.next_react_text()
    assert len(session.messages)==2 and not session.last_actions


def test_unknown_tool_has_explicit_result(monkeypatch):
    results,_,_,_=run(monkeypatch,[('nonexistent_tool',{}),('get_current_directory',{})],
        {'get_current_directory':lambda:{'success':True,'message':'ok'}})
    assert [r['code'] for r in results]==['UNKNOWN_TOOL','SUCCESS']


def test_preflight_entire_batch_precedes_first_handler(monkeypatch):
    from sys_agent.tool_executor import ToolExecutor
    events=[]
    original=ToolExecutor.preflight
    def check(self,name,args):
        events.append('check')
        return original(self,name,args)
    monkeypatch.setattr(ToolExecutor,'preflight',check)
    def handler():
        assert events[:2]==['check','check']
        events.append('execute')
        return {'success':True,'message':'ok'}
    run(monkeypatch,[('get_current_directory',{}),('list_running_applications',{})],
        {'get_current_directory':handler,'list_running_applications':handler})


def test_unregistered_known_dangerous_tool_aborts_whole_batch(monkeypatch):
    monkeypatch.delenv('DEEPSHELL_ENABLE_ALL_TOOLS',raising=False)
    client=FakeClient([batch([('get_current_directory',{}),('shutdown_system',{})])])
    calls=[]
    schemas=[s for s in load_existing_tool_schemas() if s['name'] in ('get_current_directory','shutdown_system')]
    agent=ReActAgent('fake',schemas,{'get_current_directory':lambda:calls.append('read')},lambda *_:None,
        lambda *_:None,lambda *_:None,lambda *_:None,lambda:False,tool_call_mode='native_fc',native_client=client,
        native_model_config=CONFIG,allow_approved_write=False)
    agent.run('test')
    results=[json.loads(m['content']) for m in agent._native_session.messages if m['role']=='tool']
    assert not calls and [r['code'] for r in results]==['SKIPPED','PERMISSION_DENIED']


@pytest.mark.parametrize('second',['approve','deny','cancel','timeout'])
def test_real_qt_sequential_batch_approvals(monkeypatch,qtbot,second):
    from PyQt5.QtCore import Qt,QTimer
    from PyQt5.QtWidgets import QDialogButtonBox,QDialog
    from ui.agent_approval_dialog import AgentApprovalDialog
    from sys_agent import react_agent
    monkeypatch.setenv('DEEPSHELL_ENABLE_ALL_TOOLS','1')
    calls,dialogs,reviews=[],[],[]
    client=FakeClient([batch([('run_program',{'command':'fake1'}),('run_program',{'command':'fake2'})]),text_response('done')])
    schema=next(s for s in load_existing_tool_schemas() if s['name']=='run_program')
    agent=ReActAgent('fake',[schema],{'run_program':lambda **a:(calls.append(a) or {'success':True,'message':'mock'})},
        lambda *_:None,lambda *_:None,lambda *_:None,lambda *_:None,lambda:False,
        tool_call_mode='native_fc',native_client=client,native_model_config=CONFIG)
    worker=react_agent._ReActWorker(agent,'synthetic')
    def review(ticket):
        reviews.append(ticket)
        assert len(calls)==len(reviews)-1
        dialog=AgentApprovalDialog(ticket['tool'],ticket['effect'],ticket['content'],ticket['sha256'],operation=True)
        dialogs.append(dialog);qtbot.addWidget(dialog)
        dialog.finished.connect(lambda code:worker.resolve_approval(ticket['request_id'],code==QDialog.Accepted))
        dialog.show()
        if len(reviews)==1 or second=='approve':
            QTimer.singleShot(0,lambda:qtbot.mouseClick(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok),Qt.LeftButton))
        elif second=='deny':
            QTimer.singleShot(0,lambda:qtbot.mouseClick(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Cancel),Qt.LeftButton))
        elif second=='cancel': worker.stop()
    if second=='timeout':monkeypatch.setattr(react_agent,'APPROVAL_WAIT_SECONDS',.1)
    worker.operation_approval_requested.connect(review)
    worker.start()
    try:
        qtbot.waitUntil(lambda:not worker.isRunning(),timeout=5000)
        assert len(reviews)==2 and len(calls)==(2 if second=='approve' else 1)
        agent._native_session._validate_messages()
        assert len([m for m in agent._native_session.messages if m['role']=='tool'])==2
    finally:
        worker.stop();assert worker.wait(2000)
        for dialog in dialogs:dialog.close()
