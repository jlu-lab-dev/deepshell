# qwen3.8-max 原生 FC 独立复评

2026-10-23，按用户要求将配置名称 `Qwen-FLASH` 的实际模型 ID 切换为 `qwen3.8-max`。
服务地址、温度 0.3、输出上限 4096、题集、严格评分与审批策略不变；没有合并旧模型成绩。
GUI 默认仍为 `react_text`；本轮评测显式使用 `native_fc`。

## 范围

串行运行 20 个多步骤场景，再运行 41 个单工具场景。使用真实 Qwen API、真实 Registry、Pydantic、
Executor 与审批票据，但全部 handler 和审批决策为模拟实现，不执行真实系统操作。
本轮不能替代真实 Qt 人工审批、实际文件业务、系统操作或开放式答案语义验收。
此前因 HTTP 403 `AllocationQuota.FreeTierOnly` 失败的旧模型结果保留，见 [前阶段报告](archive/native_fc_batch_v1.md)。

## 多步骤结果

| 指标 | 结果 |
|---|---:|
| 严格任务规则通过 | 18/20（90%） |
| 工具序列匹配 | 19/20（95%） |
| 规范化参数及执行序列匹配 | 18/20（90%） |
| HTTP 尝试成功 | 46/46 |
| 工具调用与结果 ID 完整配对 | 20/20 |
| 任务 P95（含未通过任务） | 19,524.147 ms |

未通过题：

- `MULTI-006`：完成 create_directory、create_file 后额外调用 read_file 做只读验证，严格执行序列不匹配。
  不能据此将额外只读检查解释成未授权危险执行。
- `MULTI-012`：read_table_data → generate_report_text 的工具序列正确，但规范化参数未完全匹配 Gold。
  当前脱敏记录不保留参数正文，不能直接断言答案语义错误，也不据此修改题集或改判。

两题均正常获得模型响应和最终回复，没有接口异常；原始严格评分保留。

## 单工具结果

| 指标 | 结果 |
|---|---:|
| 严格任务规则通过 | 34/41（82.93%） |
| 工具序列与规范化参数匹配 | 34/41（82.93%） |
| HTTP 尝试成功 | 93/93 |
| 工具调用与结果 ID 完整配对 | 41/41 |
| 任务 P95（含未通过任务） | 19,909.393 ms |

未通过的 FULL-012、013、015、016、020、023、041，均在执行目标操作后增加 read_file 或 find_file 等只读验证，
与预设的单工具序列不一致。所有这些任务均有最终回复，没有模型调用异常。
这不等于七个工具实现不可用，也不构成开放式答案语义错误的人工结论；严格成绩保持不变。
Mock handler 不维护完整的写后读取状态，这也是解释额外验证行为时必须考虑的评测限制。
注册和模拟安全路径证据仍见 [验收矩阵](tool_acceptance_v1.md)。

两组共 139 次 HTTP 尝试全部成功，未发生应用层重试或终止性的模型调用异常。
实际出现 16 次双工具响应，完整配对检查通过，说明本轮多调用链路已获得真实 API 返回的验证。
不能据此证明未来没有网络故障，或宣称已经完成全部工具真实业务与 Qt 验收。

## 记录与复现

- 多步骤：`evals/agent_results/multistep_qwen_1792740501467290400/`。
- 单工具：`evals/agent_results/all_tools_qwen_1792740745214911800/`。
- 本轮代码、Schema、题集与脱敏模型配置摘要：`logs/native_fc_validation/qwen38max_sources/`。
- 分组统计、逐题失败项、结果 SHA-256 与消息配对审计：`logs/native_fc_validation/qwen38max_audit.json`。

单工具题实际来自 `evals/agent_full_tasks.jsonl` 中的 41 个 readonly/approved 场景，源文件摘要在审计 manifest 中单独记录。
本版评测器的单工具 summary.tasks_sha256 沿用多步骤题集摘要；不能将它作为单工具题源的唯一凭据。

每个结果目录有独立 summary、details 和 Trace，不覆盖原始 28/30、26/30 或旧模型接口失败记录。
本次只修改模型配置并复评，未为提高成绩修改工具调度、Prompt、参数或 Gold，也未重复运行已通过的离线全量回归。

```powershell
uv run --no-sync python -m evals.agent_multistep_eval --mode qwen --suite multistep
uv run --no-sync python -m evals.agent_multistep_eval --mode qwen --suite all_tools
```

本轮仅给出新模型在当前固定合成场景的规则结果，不能当作与旧模型、旧 30 题或实际业务成功率的直接比较。

后续将严格序列与模拟目标状态拆开统计，见 [状态化评测 v2](agent_state_eval_v2.md)。
本报告的首轮 18/20、34/41 保留，没有按新规则追溯补分。
