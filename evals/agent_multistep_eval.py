"""原生 FC 多工具评测。真实 Qwen + 全部模拟 handler + 脚本审批；不操作真实系统。"""
import argparse
from copy import deepcopy
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
from types import SimpleNamespace as NS

from evals.agent_eval import load_existing_tool_schemas
from evals.agent_full_eval import read_tasks as old_tasks, full_profile, fake_output, canonical_step, WORKSPACE
from sys_agent.react_agent import ReActAgent
from sys_agent.agent_trace import TraceRecorder
from sys_agent.native_fc_session import RequestPolicy

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'evals/agent_multistep_tasks.jsonl'


def read_tasks(suite='multistep'):
    if suite=='holdout_v3':
        return [json.loads(s) for s in (ROOT/'evals/agent_state_holdout_v3.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
    if suite=='holdout':
        return [json.loads(s) for s in (ROOT/'evals/agent_state_holdout.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
    if suite=='all_tools':
        return [dict(id=t['id'],question=t['question'],batches=[t['expected_steps']],approval='approve',state_contract=t.get('state_contract'))
                for t in old_tasks() if t['category'] in ('readonly','approved')]
    tasks=[json.loads(s) for s in DATA.read_text(encoding='utf-8').splitlines() if s.strip()]
    if len(tasks)!=20 or len({t['id'] for t in tasks})!=20: raise ValueError('需要20个唯一任务')
    return tasks


def select_tasks(tasks, task_ids=None):
    if task_ids is None:
        return tasks
    wanted=[x.strip() for x in task_ids.split(',')]
    if not all(wanted) or len(wanted)!=len(set(wanted)):
        raise ValueError('题号不得为空或重复')
    unknown=set(wanted)-{t['id'] for t in tasks}
    if unknown:
        raise ValueError('未知题号: '+','.join(sorted(unknown)))
    return [t for t in tasks if t['id'] in set(wanted)]


def run_one(task,mode,trace_dir,stateful=False,contract_version=2,model='Qwen-FLASH',model_id=None):
    from config.config_manager import ConfigManager
    calls,final,errors,thoughts,approvals=[],[],[],[],[]
    from evals.agent_state import StateWorld,contract_for
    steps=[s for group in task['batches'] for s in group]
    if stateful and contract_version==3:
        from evals.agent_state_v3 import StateWorldV3
        from evals.task_scope import contract_v3
        world=StateWorldV3(contract_v3(steps, initial_files=task.get('initial_files')))
    else:
        world=StateWorld(task.get('state_contract') or contract_for(steps)) if stateful else None
    def invoke(name,args):
        calls.append({'tool':name,'args':deepcopy(args)})
        return world.invoke(name,args) if world else fake_output(name,args)
    schemas=load_existing_tool_schemas()
    handlers={s['name']:(lambda name:lambda **args:invoke(name,args))(s['name']) for s in schemas}
    trace=TraceRecorder(trace_dir,task_id=task['id'])
    client,config=None,None
    if mode!='mock' and model_id is not None:
        config=deepcopy(ConfigManager().get_model_config(model))
        if not config:
            raise ValueError('模型配置不存在')
        config['model_name']=model_id
    if mode=='mock':
        batches=iter(task['batches'])
        number=[0]
        def create(**kwargs):
            number[0]+=1
            current=next(batches,None)
            tool_calls=[NS(id=f'call_{number[0]}_{i}',type='function',function=NS(name=a['tool'],arguments=json.dumps(a['args'])))
                        for i,a in enumerate(current)] if current else []
            return NS(choices=[NS(message=NS(content=None if current else '已完成模拟任务。',tool_calls=tool_calls))])
        client=NS(chat=NS(completions=NS(create=create)))
        config=dict(type='openai_compatible',api_base='https://example.invalid',api_key='fake',model_name='mock')
    def approve(review):
        approvals.append(review.get('tool','create_text_file'))
        return task['approval']=='approve' and (world.approve(review) if world else True)
    agent=ReActAgent(model,schemas,handlers,lambda *_:None,lambda *_:None,final.append,errors.append,
        lambda:False,thought_chain_collector=thoughts.append,trace_recorder=trace,tool_call_mode='native_fc',
        native_client=client,native_model_config=config,approval_cb=approve,
        native_request_policy=RequestPolicy(max_retries=1))
    if stateful and contract_version==3:
        agent.executor.access_policy=world.policy
        world.read_observer=lambda name,args: calls.append({'tool':name,'args':deepcopy(args)})
    def create_approved_text(filename,content):
        outcome=invoke('create_text_file',dict(filename=filename,content=content))
        if not outcome['success']:
            raise RuntimeError('模拟文件创建未完成')
        return str(WORKSPACE/filename)
    agent.executor.approvals.writer=NS(root=WORKSPACE,create=create_approved_text)
    agent.run(task['question'])
    expected=[s for group in task['batches'] for s in group]
    canonical=lambda seq:[canonical_step(s,agent.tool_registry) for s in seq]
    correct=canonical(calls)==canonical(expected)
    selected=[t['action']['tool'] for t in thoughts if isinstance(t.get('action'),dict)]
    messages=agent._native_session.messages if agent._native_session else []
    tool_ids=[c['id'] for m in messages for c in m.get('tool_calls',[])]
    result_ids=[m['tool_call_id'] for m in messages if m['role']=='tool']
    paired=tool_ids==result_ids and len(set(tool_ids))==len(tool_ids)
    requests=[e for e in trace.events if e['event']=='model_request']
    result=dict(task_id=task['id'],rule_pass=bool(correct and paired and final and not errors),
        execution_correct=correct,tool_messages_paired=paired,handler_calls=len(calls),
        tool_selection_correct=selected==[s['tool'] for s in expected],decision_observed=bool(selected),
        tools_executed=[c['tool'] for c in calls],approval_count=len(approvals),
        api_attempts=len(requests),api_successes=sum(e['success'] for e in requests),
        model_errors=[e.get('error_kind') for e in trace.events if e['event']=='model_result' and e.get('success') is False],
        terminal_http_status=next((e['http_status'] for e in reversed(trace.events) if e.get('http_status') and e.get('success') is False),None),
        trace_id=trace.trace_id,answer_present=bool(final),elapsed_ms=trace.events[-1].get('elapsed_ms'),
        runtime_revision='tool_recovery_v1',runtime_status=agent.runtime_status(),
        model_alias=model,model_id='mock' if mode=='mock' else (model_id or ConfigManager().get_model_config(model)['model_name']))
    if world:
        result.update(world.score())
        result['strict_sequence_match']=correct
        result['task_success']=bool(result['state_goal_met'] and result['safe'] and paired and final and not errors)
    return result


def main():
    from config.config_manager import ConfigManager
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['mock','qwen','live'],default='mock')
    parser.add_argument('--model',default='Qwen-FLASH',help='复用已有模型配置的接口与凭据')
    parser.add_argument('--model-id',help='仅为本次评测覆盖模型 ID，不修改配置文件')
    parser.add_argument('--task-ids',help='只运行这些题号，逗号分隔；未知或重复题号报错')
    parser.add_argument('--suite',choices=['multistep','all_tools','holdout','holdout_v3'],default='multistep')
    parser.add_argument('--stateful',action='store_true')
    parser.add_argument('--contract-version',type=int,choices=[2,3],default=2)
    args=parser.parse_args()
    if args.contract_version==3:
        args.stateful=True
    if args.suite=='holdout_v3' and args.contract_version!=3:
        parser.error('holdout_v3 requires --contract-version 3')
    all_tasks=read_tasks(args.suite)
    try:
        tasks=select_tasks(all_tasks,args.task_ids)
    except ValueError as exc:
        parser.error(str(exc))
    directory=ROOT/'evals/agent_results'/f'{args.suite}_{("state_v"+str(args.contract_version)+"_") if args.stateful else ""}{args.mode}_{time.time_ns()}'
    directory.mkdir(parents=True)
    print('result_dir='+str(directory),flush=True)
    rows=[]
    with full_profile():
        for task in tasks:
            row=run_one(task,args.mode,directory/'traces',stateful=args.stateful,contract_version=args.contract_version,model=args.model,model_id=args.model_id);rows.append(row)
            with (directory/'details.jsonl').open('a',encoding='utf-8') as out:out.write(json.dumps(row,ensure_ascii=False)+'\n')
            summary=dict(mode=args.mode,suite=args.suite,count=len(rows),passed=sum(r['rule_pass'] for r in rows),
                runtime_revision='tool_recovery_v1',
                planned=len(tasks),complete=len(rows)==len(tasks),source_suite_count=len(all_tasks),
                selected_task_ids=[t['id'] for t in tasks],model_alias=args.model,
                warning='所有系统工具均为模拟实现；不代表真实业务、真实GUI或开放式答案正确率。',
                api_attempts=sum(r['api_attempts'] for r in rows),api_successes=sum(r['api_successes'] for r in rows),
                tool_selection_rate=sum(r['tool_selection_correct'] for r in rows)/len(rows),
                execution_correct_rate=sum(r['execution_correct'] for r in rows)/len(rows),
                observed_decision_count=sum(r['decision_observed'] for r in rows),
                observed_tool_selection_rate=(sum(r['tool_selection_correct'] for r in rows if r['decision_observed'])/
                    sum(r['decision_observed'] for r in rows)) if any(r['decision_observed'] for r in rows) else None,
                model_id=row['model_id'],
                tasks_sha256=hashlib.sha256((ROOT/'evals/agent_full_tasks.jsonl' if args.suite=='all_tools' else ROOT/'evals/agent_state_holdout.jsonl' if args.suite=='holdout' else ROOT/'evals/agent_state_holdout_v3.jsonl' if args.suite=='holdout_v3' else DATA).read_bytes()).hexdigest())
            if args.stateful:
                summary.update(eval_version=args.contract_version,task_success=sum(r['task_success'] for r in rows),
                    task_success_rate=sum(r['task_success'] for r in rows)/len(rows),
                    strict_sequence_match=sum(r['strict_sequence_match'] for r in rows),
                    safety_violations=sum(len(r['safety_violations']) for r in rows),
                    extra_tool_calls=sum(r['extra_tool_calls'] for r in rows))
                if args.contract_version==3:
                    summary.update(read_calls=sum(r['read_calls'] for r in rows),
                                   read_handler_ms=round(sum(r['read_handler_ms'] for r in rows),3),
                                   read_result_bytes=sum(r['read_result_bytes'] for r in rows))
            (directory/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
            print(f'{row["task_id"]}: strict={row["rule_pass"]}' + (f' task={row["task_success"]}' if args.stateful else ''),flush=True)
            if row['terminal_http_status'] in (400,401,403,404):
                summary.update(complete=False,stop_reason=f'HTTP_{row["terminal_http_status"]}')
                (directory/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
                print('接口拒绝请求，停止后续场景，保留已运行记录。',flush=True)
                break


if __name__=='__main__':main()
