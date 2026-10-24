# 多 Tool Call 顺序调度与分级验收

2026-10-23。已接入顺序批次调度、41 工具合同检查和 20 题多步骤评测入口。
真实 Qwen 当前返回 403 `AllocationQuota.FreeTierOnly`，本轮未获得有效模型决策成绩。
GUI 默认仍为 `react_text`，MCP 暂停；旧成绩和独立实验结果均保留。
随后切换 `qwen3.8-max` 的独立复评见 [新模型报告](../native_fc_batch_qwen38max.md)；本文保留旧模型接口失败记录。

## 协议与执行边界

NativeFCSession 接受每轮最多 8 个调用，`parallel_tool_calls=true` 允许模型返回列表；应用不并发执行工具。
先检查整批 ID、数量与结构，再调用 Executor.preflight 检查权限和严格 Pydantic 参数。
重复/缺失 ID、超量调用在任何 handler 执行前拒绝整批，不提交不完整 assistant 消息。
每个已接受调用均有对应 ToolMessage，包括参数错误、未知工具、取消、跳过的调用。
混合批次 JSON 参数解析失败变为该项 INVALID_ARGS；单调用非法 JSON 保留原先的协议错误处理。
结果未齐全不能再次请求模型，也不能向已经消耗的 ID 再次提交结果。
对应关系依据 [OpenAI Function calling 文档](https://developers.openai.com/api/docs/guides/function-calling)。

整批包含未授权工具时不执行任何 handler。写操作逐项申请审批，没有批量授权。
拒绝、关闭或审批超时停止后续执行；取消仍补齐本地消息，随后不再请求模型。
普通工具失败后可完成该批只读查询，跳过后续写操作并结束；可恢复参数错误可回传模型修正。
原生任务上限为 24 个调用、同工具 8 次、调度时间 120 秒，并受既有网络预算与轮次限制。
这些是调度限制，不会强制中断已运行的同步 Python handler。
本轮没有实现持久化 operation_id、UNKNOWN 状态核对或跨重启幂等；重复 ID 和一次性审批不能替代完整业务幂等。

## 离线与 Qt 验证

最终完整回归：452 passed、7 skipped，另有 6 个既有依赖/环境警告。联网用例默认跳过。

- 多调用、协议、网络恢复定向回归：80 项通过。
- 整批预检查、未授权拒绝、真实 Qt 两次顺序审批的批准/拒绝/取消/超时及 20 题 Mock：37 项通过。
- 多步骤 Mock：20/20；真实 Registry、Pydantic、Executor、审批票据与消息协议，handler 全部模拟。
- 41 工具均完成 Schema、真实函数签名、合法参数、额外参数拒绝和模拟调度检查；31 个审批工具另验证拒绝和批准。

逐工具记录见 [41 工具验收表](../tool_acceptance_v1.md)。真实业务及逐项 Qt 明确标为待验收。
不能将合同或 Mock 成绩解释为所有工具真实可用、真实业务成功或模型正确率。
Qt 批次测试使用两个模拟 run_program，真实控件逐项审批，绝不执行 Shell。
本轮保留原有网络分类、预算、恢复、普通聊天/RAG 及历史回放回归。

## 真实模型接口受限

模型配置 `Qwen-FLASH`，实际 ID `qwen3.7-flash`，服务 DashScope。
20 个多步骤题和 41 个单工具题均在模型请求阶段 HTTP 403，handler 执行次数为零。
一次不含工具与系统数据的最小请求确认错误码为 `AllocationQuota.FreeTierOnly`。
记录只证明接口当前不可用，不评价模型工具选择、参数或多步骤能力；没有自动换模型或覆盖旧成绩。

- `evals/agent_results/multistep_mock_1792739696878610400/`：Mock 20/20。
- `evals/agent_results/multistep_qwen_1792739733782857200/`：20 个接口失败任务。
- `evals/agent_results/all_tools_qwen_1792739742443105600/`：41 个接口失败任务。
- `evals/agent_results/tool_acceptance_1792739878229035200/matrix.json`：41 工具合同证据。

API 失败算端到端未完成；没有有效响应时不能算模型选错工具。空调用的配对一致也不代表任务完成。
任务评分要求规范化参数和 handler 序列正确、存在最终回复；不审核开放式答案语义。
新题集包含独立查询、文件整理、表格读取后报告生成、联系人后邮件草稿等，路径和内容均为合成数据。
真实 Qwen 模式仍使用模拟 handler 和脚本审批，不能替代真实业务或人工 Qt 验收。

## 复现

```powershell
uv run --no-sync python -m evals.tool_acceptance
uv run --no-sync python -m evals.agent_multistep_eval --mode mock
uv run --no-sync python -m pytest tests/test_native_fc_batch.py tests/test_agent_multistep_eval.py -q
```

额度恢复后分别运行，每次产生新目录：

```powershell
uv run --no-sync python -m evals.agent_multistep_eval --mode qwen --suite multistep
uv run --no-sync python -m evals.agent_multistep_eval --mode qwen --suite all_tools
```

下一步仍需有效的真实模型成绩、实际业务分级验收和幂等边界，再考虑默认切换与 MCP。
