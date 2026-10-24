import json
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest

from evals.agent_eval import load_existing_tool_schemas
from evals.agent_full_eval import FILE_CONTENT
from evals.agent_state import path
from evals.agent_state_v3 import StateWorldV3
from evals.task_scope import contract_v3
from sys_agent.object_access import ObjectAccessPolicy
from sys_agent.sandbox_file import SandboxError, resolve_object_path
from sys_agent.tool_executor import ToolExecutor
from sys_agent.tool_registry import ToolRegistry

ROOT = 'D:/AgentEvalSandbox'


def environment(monkeypatch, steps, fixtures=None, **limits):
    monkeypatch.setenv('DEEPSHELL_ENABLE_ALL_TOOLS','1')
    monkeypatch.setenv('DEEPSHELL_ENABLE_APPROVED_WRITE','1')
    world = StateWorldV3(contract_v3(steps,initial_files=fixtures))
    if limits:
        world.policy = ObjectAccessPolicy(replace(world.policy.scope,**limits),world,
                                         lambda n,a: world.permitted_operation({'tool':n,'args':a}) is not None,
                                         virtual=True)
    schemas = load_existing_tool_schemas()
    handlers = {s['name']:(lambda n:lambda **a:world.invoke(n,a))(s['name']) for s in schemas}
    executor = ToolExecutor(ToolRegistry.from_existing(schemas,handlers),world.policy)
    def write(filename,content):
        result=world.invoke('create_text_file',{'filename':filename,'content':content})
        if not result['success']:
            raise OSError('simulated failure')
        return ROOT+'/workspace/'+filename
    executor.approvals.writer=NS(root=ROOT+'/workspace',create=write)
    return world,executor


def approved(world,executor,tool,args):
    pending=executor.execute(tool,args)
    assert pending.code=='PENDING_APPROVAL'
    request=pending.data['request_id']
    assert world.approve(executor.get_pending_approval(request))
    return executor.resolve_pending_approval(request,True)


@pytest.mark.parametrize('tool',['rename_file','copy_file','move_file'])
def test_prechecks_and_final_content_are_consistent(monkeypatch,tool):
    src,dst=ROOT+'/source.txt',ROOT+'/fresh.txt'
    world,executor=environment(monkeypatch,[{'tool':tool,'args':{'src':src,'dst':dst}}])
    assert executor.execute('read_file',{'path':src}).data['content']==FILE_CONTENT
    missing=executor.execute('find_file',{'path':ROOT,'filename':'fresh.txt'})
    assert missing.success and missing.data['found_paths']==[]
    assert approved(world,executor,tool,{'src':src,'dst':dst}).success
    assert executor.execute('read_file',{'path':dst}).data['content']==FILE_CONTENT
    assert (path(src) in world.files)==(tool=='copy_file')
    assert world.score()['state_goal_met'] and world.score()['safe']


def test_scope_projection_never_enumerates_decoys(monkeypatch):
    args={'src':ROOT+'/source.txt','dst':ROOT+'/fresh.txt'}
    world,executor=environment(monkeypatch,[{'tool':'rename_file','args':args}],
                               {ROOT+'/source_secret.txt':'secret'})
    result=executor.execute('find_file',{'path':ROOT,'filename':'source','nums':-1})
    assert result.success and result.data['scoped_lookup']
    assert result.data['found_paths']==[path(args['src'])]
    forbidden=executor.execute('read_file',{'path':ROOT+'/source_secret.txt'})
    assert forbidden.code=='OBJECT_OUT_OF_SCOPE' and 'secret' not in forbidden.model_dump_json()
    assert len(world.calls)==1


@pytest.mark.parametrize('bad',[ROOT+'/../outside.txt',ROOT+'/a/../../escape.txt',
    ROOT+'Other/file.txt',ROOT+'/CON.txt',ROOT+'/a.txt:secret',ROOT+'/name.txt.',
    r'\\server\share\a.txt',ROOT+'/NUL',ROOT+'/a/./file.txt'])
def test_shared_path_resolver_rejects_aliases_and_traversal(bad):
    with pytest.raises(SandboxError):
        resolve_object_path(bad,ROOT,virtual=True)


def test_executor_checks_raw_traversal_before_path_freezing(monkeypatch):
    step={'tool':'create_file','args':{'path':ROOT+'/fresh.txt','content':'required'}}
    world,executor=environment(monkeypatch,[step])
    result=executor.execute('create_file',{'path':ROOT+'/sub/../fresh.txt','content':'required'})
    assert result.code=='INVALID_OBJECT_PATH' and not world.calls


def test_approval_does_not_bypass_new_destination_collision(monkeypatch):
    args={'src':ROOT+'/source.txt','dst':ROOT+'/fresh.txt'}
    world,executor=environment(monkeypatch,[{'tool':'rename_file','args':args}])
    pending=executor.execute('rename_file',args)
    world.files[path(args['dst'])]='protected'
    request=pending.data['request_id']
    assert world.approve(executor.get_pending_approval(request))
    result=executor.resolve_pending_approval(request,True)
    assert result.code=='TARGET_EXISTS' and not world.calls
    assert world.files[path(args['dst'])]=='protected' and path(args['src']) in world.files
    assert executor.resolve_pending_approval(request,True).code=='APPROVAL_INVALID'


def test_repeat_effect_and_wrong_content_are_rejected(monkeypatch):
    step={'tool':'create_file','args':{'path':ROOT+'/fresh.txt','content':'required'}}
    world,executor=environment(monkeypatch,[step])
    assert executor.execute('create_file',{**step['args'],'content':'wrong'}).code=='TASK_ARGUMENT_MISMATCH'
    assert approved(world,executor,step['tool'],step['args']).success
    assert not executor.execute(step['tool'],step['args']).success
    assert len(world.calls)==1 and world.files[path(step['args']['path'])]=='required'


def test_write_without_approval_has_no_side_effect(monkeypatch):
    step={'tool':'create_file','args':{'path':ROOT+'/fresh.txt','content':'required'}}
    world,executor=environment(monkeypatch,[step])
    result=executor.execute(step['tool'],step['args'])
    assert result.code=='PENDING_APPROVAL' and not world.calls
    assert path(step['args']['path']) not in world.files


def test_read_budget_is_consumed_only_at_execution(monkeypatch):
    step={'tool':'read_file','args':{'path':ROOT+'/source.txt'}}
    world,executor=environment(monkeypatch,[step],max_read_calls=1)
    assert executor.preflight(step['tool'],step['args']) is None
    assert executor.preflight(step['tool'],step['args']) is None
    assert world.policy.read_calls==0
    assert executor.execute(step['tool'],step['args']).success
    assert executor.execute(step['tool'],step['args']).code=='READ_BUDGET_EXCEEDED'
    assert world.policy.read_calls==1 and len(world.calls)==1


def test_file_size_is_checked_before_handler(monkeypatch):
    step={'tool':'read_file','args':{'path':ROOT+'/source.txt'}}
    world,executor=environment(monkeypatch,[step],{ROOT+'/source.txt':'x'*20000})
    assert executor.execute(step['tool'],step['args']).code=='FILE_SIZE_LIMIT'
    assert not world.calls


@pytest.mark.parametrize('mode',['bytes','objects'])
def test_bad_handler_results_never_reach_observation(monkeypatch,mode):
    step={'tool':'read_file','args':{'path':ROOT+'/source.txt'}}
    world,executor=environment(monkeypatch,[step],max_result_bytes=200)
    handler=(lambda **_: {'success':True,'content':'x'*500}) if mode=='bytes' else (
        lambda **_: {'success':True,'found_paths':[ROOT+'/secret.txt']})
    world.read_objects=lambda *unused: handler()
    result=executor._invoke('read_file',lambda **_:pytest.fail('ambient handler called'),step['args'])
    assert not result.success and not result.data


def test_corrupt_copy_content_cannot_pass_state_oracle(monkeypatch):
    step={'tool':'copy_file','args':{'src':ROOT+'/source.txt','dst':ROOT+'/fresh.txt'}}
    world,executor=environment(monkeypatch,[step])
    assert approved(world,executor,step['tool'],step['args']).success
    world.files[path(step['args']['dst'])]='wrong'
    assert not world.score()['state_goal_met']


@pytest.mark.parametrize('suite',['all_tools','multistep','holdout','holdout_v3'])
def test_v3_mock_regression_and_new_objects(suite,tmp_path):
    from evals.agent_full_eval import full_profile
    from evals.agent_multistep_eval import read_tasks,run_one
    with full_profile():
        rows=[run_one(task,'mock',tmp_path/suite,stateful=True,contract_version=3) for task in read_tasks(suite)]
    assert all(r['task_success'] and r['tool_messages_paired'] for r in rows), [r for r in rows if not r['task_success']]


def test_invalid_batch_template_returns_error_not_exception(monkeypatch):
    step={'tool':'batch_rename_files','args':{'file_paths':[ROOT+'/a.txt'],'rename_pattern':'renamed-{num}'}}
    world,executor=environment(monkeypatch,[step])
    result=executor.execute(step['tool'],{**step['args'],'rename_pattern':'{unknown}'})
    assert result.code=='TASK_ARGUMENT_MISMATCH' and not world.calls


@pytest.mark.parametrize('tool,args,target',[
    ('write_file',{'path':ROOT+'/existing.txt','content':'new'},ROOT+'/existing.txt'),
    ('save_text_as_word_doc',{'directory':ROOT,'filename':'report.docx','content':'new'},ROOT+'/report.docx'),
])
def test_explicit_overwrite_tools_still_require_exact_goal_and_approval(monkeypatch,tool,args,target):
    world,executor=environment(monkeypatch,[{'tool':tool,'args':args}])
    before=world.files[path(target)]
    pending=executor.execute(tool,args)
    assert pending.code=='PENDING_APPROVAL' and world.files[path(target)]==before
    request=pending.data['request_id']
    assert world.approve(executor.get_pending_approval(request))
    assert executor.resolve_pending_approval(request,True).success
    assert world.files[path(target)]=='new' and world.score()['state_goal_met']


def test_lookup_result_limit_and_aggregate_bytes(monkeypatch):
    step={'tool':'copy_file','args':{'src':ROOT+'/source.txt','dst':ROOT+'/fresh.txt'}}
    world,executor=environment(monkeypatch,[step],max_results=1,max_total_result_bytes=1)
    result=executor.execute('find_files_by_extension',{'directory':ROOT,'extensions':['.txt']})
    assert result.code=='READ_RESULT_LIMIT' and not result.data


def test_real_resolver_rejects_link_chain(tmp_path):
    from sys_agent.sandbox_file import resolve_object_path
    root=tmp_path/'workspace';root.mkdir()
    outside=tmp_path/'outside';outside.mkdir()
    link=root/'link'
    try:
        link.symlink_to(outside,target_is_directory=True)
    except OSError:
        pytest.skip('symlink privilege unavailable')
    with pytest.raises(SandboxError):
        resolve_object_path(str(link/'file.txt'),str(root))


def test_batch_duplicate_source_is_rejected_atomically(monkeypatch):
    args={'file_paths':[ROOT+'/a.txt',ROOT+'/a.txt'],'prefix':'new_'}
    world,executor=environment(monkeypatch,[{'tool':'batch_add_prefix_to_filenames','args':args}])
    before=dict(world.files)
    assert executor.execute('batch_add_prefix_to_filenames',args).code=='DUPLICATE_SOURCE'
    assert world.files==before and not world.calls


def test_reparse_metadata_rejected_without_symlink_privilege(tmp_path,monkeypatch):
    import stat
    from pathlib import Path
    root=tmp_path/'root';root.mkdir()
    junction=root/'junction';junction.mkdir()
    original=Path.lstat
    def lstat(p,*a,**kw):
        if p==junction:
            return NS(st_mode=stat.S_IFDIR,st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
        return original(p,*a,**kw)
    monkeypatch.setattr(Path,'lstat',lstat)
    with pytest.raises(SandboxError):
        resolve_object_path(str(junction/'file.txt'),str(root))


def test_scoped_lookup_never_calls_ambient_handler(monkeypatch):
    step={'tool':'copy_file','args':{'src':ROOT+'/source.txt','dst':ROOT+'/fresh.txt'}}
    world,executor=environment(monkeypatch,[step],{ROOT+'/source_secret.txt':'secret'})
    result=executor._invoke('find_file',lambda **_:pytest.fail('ambient enumeration called'),
                            {'path':ROOT,'filename':'source'})
    assert result.success and result.data['found_paths']==[path(step['args']['src'])]
