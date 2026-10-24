"""串行原生 FC 稳定性排查；只发送固定问题与模拟工具，不接入系统 handler。

A: 重复相同只读 FC 请求；B: 普通聊天/FC 交替；C/D: 相同 SDK/策略的原始 30 题。
不与历史成绩合并。默认零重试用于暴露首次请求故障；生产恢复策略另由离线注入验证。
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import time
from urllib.parse import urlsplit

from evals.agent_eval import DATA, ROOT, aggregate, controlled_prompt, load_existing_tool_schemas, read_tasks, run_one
from sys_agent.agent_trace import TraceRecorder
from sys_agent.native_fc_session import NativeFCSession, RequestPolicy, classify_model_error


def percentile(values):
    return sorted(values)[math.ceil(len(values)*.95)-1] if values else None


def summarize(rows):
    attempts = sum(r.get('api_attempts') or 0 for r in rows)
    successes = sum(r.get('api_successes') or 0 for r in rows)
    safe = [r for r in rows if r.get('category') == 'safe_tool' and r.get('decision_observed')]
    return dict(count=len(rows), api_attempts=attempts, api_successes=successes,
        api_success_rate=successes/attempts if attempts else None,
        retries=sum(r.get('retries') or 0 for r in rows),
        classified_errors=dict(Counter(e for r in rows for e in r.get('api_errors', r.get('model_errors', [])))),
        terminal_model_errors=dict(Counter(e for r in rows for e in r.get('model_errors', []))),
        end_to_end_rule_pass=sum(r['rule_pass'] for r in rows),
        end_to_end_rule_rate=sum(r['rule_pass'] for r in rows)/len(rows) if rows else None,
        observed_tool_decision_count=len(safe),
        observed_tool_selection_correct=sum(r['selected_expected_tool'] for r in safe),
        observed_tool_selection_rate=sum(r['selected_expected_tool'] for r in safe)/len(safe) if safe else None,
        p95_all_ms=percentile([r['elapsed_ms'] for r in rows]),
        p95_rule_pass_ms=percentile([r['elapsed_ms'] for r in rows if r['rule_pass']]))


def probe(config, policy, trace_dir, phase, number, with_tools):
    trace = TraceRecorder(trace_dir, task_id=f'{phase}-{number:03d}')
    trace.record('task_started', model_name='Qwen-FLASH')
    schema = next(s for s in load_existing_tool_schemas() if s['name'] == 'get_current_directory')
    session = NativeFCSession(config, [schema] if with_tools else [], history=[],
        user_input='查询当前工作目录。', permission_text='仅可调用列出的只读工具；不可执行写入、删除、Shell 或关机。',
        policy=policy, observer=lambda **e: trace.record('model_request', **e))
    started = time.perf_counter()
    passed, error = False, []
    try:
        session.next_react_text()
        passed = (session.last_action == {'tool':'get_current_directory','args':{}} if with_tools
                  else bool(session.last_answer))
        trace.finish('completed')
    except Exception as exc:
        metadata = classify_model_error(exc)
        error.append(metadata['error_kind'])
        trace.record('model_result', success=False, **metadata)
        trace.finish('model_error')
    finally:
        session.close()
    return dict(phase=phase, task_id=trace.task_id, trace_id=trace.trace_id,
        with_tools=with_tools, api_attempts=len(session.request_events),
        api_successes=sum(e['success'] for e in session.request_events),
        api_errors=[e['error_kind'] for e in session.request_events if not e['success']],
        retries=sum(e['attempt'] > 1 for e in session.request_events),
        model_errors=error, rule_pass=passed, elapsed_ms=round((time.perf_counter()-started)*1000,3))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='Qwen-FLASH')
    parser.add_argument('--phase', choices=['api','load','tasks','all'], default='all')
    parser.add_argument('--repeats', type=int, default=50)
    parser.add_argument('--pairs', type=int, default=10)
    parser.add_argument('--request-timeout', type=float, default=20)
    parser.add_argument('--task-budget', type=float, default=90)
    parser.add_argument('--max-retries', type=int, default=0)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'evals/agent_results')
    args=parser.parse_args()
    if args.repeats < 1 or args.pairs < 1: parser.error('repeats/pairs 必须为正整数')
    policy=RequestPolicy(args.request_timeout,args.task_budget,args.max_retries)
    from config.config_manager import ConfigManager
    config=ConfigManager().get_model_config(args.model)
    run_dir=args.output_dir/f'reliability_{time.time_ns()}'
    run_dir.mkdir(parents=True)
    sources=[ROOT/f for f in ('sys_agent/native_fc_session.py','sys_agent/react_agent.py',
        'sys_agent/agent_trace.py','chat/model_manager.py','evals/agent_eval.py',
        'evals/native_fc_stability.py','config/assistant.yaml','config/app.yaml','evals/agent_tasks.jsonl')]
    sources.extend(sorted((ROOT/'sys_agent/toolkits').glob('*.json')))
    manifest=dict(model=args.model, model_id=config['model_name'], endpoint_host=urlsplit(config['api_base']).hostname,
        temperature=config.get('temperature'),max_tokens=config.get('max_tokens'), thinking='not explicitly configured; same provider defaults',
        stream=False, sdk_max_retries=0, policy=vars(policy), concurrency=1,
        phases=args.phase,repeats=args.repeats,pairs=args.pairs,
        sdk_versions={p:importlib.metadata.version(p) for p in ('openai','httpx','langchain-community')},
        source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (run_dir/'sources').mkdir()
    for path in sources:
        copy=run_dir/'sources'/path.relative_to(ROOT)
        copy.parent.mkdir(parents=True,exist_ok=True)
        copy.write_bytes(path.read_bytes())
    (run_dir/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    rows=[]
    def save(row):
        rows.append(row)
        with (run_dir/'details.jsonl').open('a',encoding='utf-8') as out:
            out.write(json.dumps(row,ensure_ascii=False)+'\n')
        groups=sorted({r['phase'] for r in rows})
        summary={'complete':False,'groups':{g:summarize([r for r in rows if r['phase']==g]) for g in groups}}
        (run_dir/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'phase':row['phase'],'task_id':row['task_id'],'pass':row['rule_pass'],
                          'errors':row['model_errors'],'elapsed_ms':row['elapsed_ms']},ensure_ascii=False),flush=True)
    print('result_dir='+str(run_dir),flush=True)
    if args.phase in ('api','all'):
        for i in range(1,args.repeats+1): save(probe(config,policy,run_dir/'traces','A_fc_repeat',i,True))
    if args.phase in ('load','all'):
        for i in range(1,args.pairs+1):
            save(probe(config,policy,run_dir/'traces','B_chat',i,False))
            save(probe(config,policy,run_dir/'traces','B_fc',i,True))
    if args.phase in ('tasks','all'):
        # 完整文本组结束后才开始原生组；不启动第二个进程或后台请求。
        for protocol in ('react_text','native_fc'):
            for task in read_tasks(DATA):
                row=run_one(task,'qwen',args.model,run_dir/'traces',protocol,controlled=True,request_policy=policy)
                save({'phase':'CD_'+protocol,**row})
    summary=json.loads((run_dir/'summary.json').read_text(encoding='utf-8'))
    summary['complete']=True
    summary['note']='API 按每次 HTTP 尝试统计；工具选择分母为已观察到 Action 的只读题；全部任务仍计入端到端分母。旧成绩不覆盖。'
    (run_dir/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print('complete='+str(run_dir),flush=True)


if __name__ == '__main__': main()
