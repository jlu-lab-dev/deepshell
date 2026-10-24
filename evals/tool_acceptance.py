"""41 工具分级验收矩阵：真实 Schema/签名/Executor，模拟副作用 handler。"""
import inspect
import json
from pathlib import Path
import time
from types import SimpleNamespace as NS
from evals.agent_full_eval import read_tasks,full_profile,WORKSPACE
from evals.agent_eval import load_existing_tool_schemas
from sys_agent.react_agent import ReActAgentController
from sys_agent.tool_registry import ToolRegistry
from sys_agent.tool_executor import ToolExecutor
from sys_agent.tool_policy import READ_ONLY_TOOL_NAMES


def audit():
    schemas,real=ReActAgentController._load_all_tools(None)
    fixtures={t['expected_steps'][0]['tool']:t['expected_steps'][0]['args'] for t in read_tasks()
              if t['category'] in ('readonly','approved')}
    rows=[]
    with full_profile():
        for name,args in fixtures.items():
            calls=[]
            handlers={s['name']:lambda **kw:(calls.append(kw) or {'success':True,'message':'mock'}) for s in schemas}
            executor=ToolExecutor(ToolRegistry.from_existing(schemas,handlers))
            executor.approvals.writer=NS(root=WORKSPACE,create=lambda filename,content:(calls.append(dict(filename=filename,content=content)) or str(WORKSPACE/'mock.txt')))
            tool=executor.registry.get(name)
            assert tool is not None
            tool.args_model.model_validate(args)
            if name in real: inspect.signature(real[name]).bind(**args)
            assert executor.execute(name,{**args,'unrecognized_field':True}).code=='INVALID_ARGS' and not calls
            needs_approval=name not in READ_ONLY_TOOL_NAMES
            if needs_approval:
                pending=executor.execute(name,args)
                assert pending.code=='PENDING_APPROVAL' and not calls
                assert executor.resolve_pending_approval(pending.data['request_id'],False).code=='APPROVAL_DENIED' and not calls
            result=executor.execute(name,args)
            if needs_approval:
                assert result.code=='PENDING_APPROVAL' and not calls
                result=executor.resolve_pending_approval(result.data['request_id'],True)
            assert result.success and len(calls)==1
            rows.append(dict(tool=name,registered=True,strict_extra_args_rejected=True,handler_signature=True,
                approval_required=needs_approval,approval_deny_verified=needs_approval,executor_mock_pass=True,
                real_business='待人工/隔离环境验收',qt_gui='未逐项验收',native_fc='本轮Qwen接口403，未完成'))
    assert len(rows)==41
    return rows


def main():
    root=Path(__file__).resolve().parents[1]
    rows=audit()
    out=root/'evals/agent_results'/f'tool_acceptance_{time.time_ns()}'
    out.mkdir(parents=True)
    (out/'matrix.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    table=['# 41 工具分级验收表','', '2026-10-23。注册、参数、签名和 Executor 安全路径已逐项验证；副作用 handler 全部模拟。',
           '不能将此表理解为全部真实业务或 Qt 操作已验收。真实原生 FC 本轮受 HTTP 403 阻碍。','',
           '| 工具 | Schema/参数/签名 | 审批路径 | Executor（模拟） | 真实业务/Qt |',
           '|---|---|---|---|---|']
    for r in rows:table.append(f'| `{r["tool"]}` | 通过 | {"批准/拒绝通过" if r["approval_required"] else "只读直接调度"} | 通过 | 待分级验收 |')
    table+=['','复现：`uv run --no-sync python -m evals.tool_acceptance`。',f'本轮机器记录：`{out.relative_to(root).as_posix()}/matrix.json`。']
    (root/'docs/experiments/tool_acceptance_v1.md').write_text('\n'.join(table)+'\n',encoding='utf-8')
    print(str(out),flush=True)


if __name__=='__main__':main()
