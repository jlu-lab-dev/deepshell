# v3 新题：DeepSeek 续测与混合模型记录

2026-10-23，按用户要求保留之前的全部结果，使用 `deepseek-v4-flash-0731`
续测 Qwen 因 HTTP 403 中断的 `OBJECT-HOLD-009`，以及未运行的 010—016，共 8 题。
没有重跑已结束的 001—008，也没有重跑其中工具失败的 004 来替换成绩。
后续 2026-10-24 使用不同模型 `deepseek-v4.1-flash-1017` 与修复后运行时完成 77 题复评，
见 [新版本完整报告](../deepseek41flash_acceptance_20261024.md)。本文的 5/8 与混合覆盖 12/16 均保留原始值。

## 模型与执行条件

沿用当前百炼 OpenAI 兼容地址 `dashscope.aliyuncs.com`，本次通过评测参数覆盖模型 ID，
不使用 DeepSeek 官方接口。基础配置别名为 `Qwen-FLASH`，实际续测模型 ID 在 summary 和每题记录中
明确保存为 `deepseek-v4-flash-0731`；别名只用于复用接口与凭据。
GUI 的模型配置仍为 `qwen3.8-max-0902`，未修改其配置文件。

温度 0.3、输出上限 4096、原生 FC、任务契约、工具、Prompt、审批及读取预算保持不变。
为可复现地选择剩余题目，评测入口新增 `--model`、`--model-id`、`--task-ids` 与通用 `--mode live`。
修改只涉及模型路由、题目选择及结果元数据，状态评分和生产运行模块保持冻结摘要一致。
定向回归 75 passed、1 skipped；跳过为既有 Windows 符号链接权限条件。

全部 handler 与审批决定仍为模拟实现，不是实际系统操作或真实 Qt 验收。

## DeepSeek 8 题结果

| 指标 | 结果 |
|---|---:|
| 已运行 / 计划 | 8/8 |
| 模拟状态任务成功 | 5/8（62.50%） |
| 仅目标对象状态满足 | 6/8 |
| 严格执行序列与参数匹配 | 0/8 |
| HTTP 尝试成功 | 25/25 |
| 工具调用/结果 ID 配对 | 8/8 |
| 契约拒绝记录 | 0 |
| 额外实际 handler 调用 | 25 |
| 受限读取调用 | 27 |
| 任务 P95（含未通过题） | 13,292.018 ms |

实际收到 11 次双工具响应，没有应用层重试、模型调用异常或接口失败。
严格匹配未通过并不等于全部任务失败：5 道成功题均使用了额外的对象核验。
目标状态与完整任务分开保留：`task_success` 还要求有最终回复、无 Agent 错误、权限及消息配对正确。

3 道未通过题保留：

| 题号 | 观察结果 | 状态与结论 |
|---|---|---|
| OBJECT-HOLD-011 | 批准并完成移动，后续一次读取返回 `TOOL_FAILED`，Agent 以 `tool_error` 结束 | 目标状态满足，但无最终回复，任务失败 |
| OBJECT-HOLD-012 | 操作前 `read_file` 返回 `TOOL_FAILED`，未创建文件 | 目标状态不满足，任务失败 |
| OBJECT-HOLD-015 | 第一次读取成功、第二次读取失败，未移动文件 | 目标状态不满足，任务失败 |

这些读取通过对象范围检查，没有权限拒绝；失败发生在工具结果及其后的 Agent 恢复路径，
不能说成 API 故障或越权执行。本轮没有修改读取语义、恢复策略、评分或题目来补分。
Trace 不保存参数正文，不能仅凭工具名称进一步归因全部具体读取目标。

## 分阶段覆盖：不是单模型成功率

原 Qwen 的 [v3 中断报告](../agent_state_eval_qwen38max0902.md) 仍保留其 **7/9** 原始结果，
其中 009 为 HTTP 403；没有覆盖这条故障记录。
下表只是将用户指定的续测结果放到独立覆盖表中，明确每题由哪个阶段完成观察：

| 阶段 | 模型 | 题号 | 状态成功 |
|---|---|---|---:|
| 原已结束任务 | qwen3.8-max-0902 | 001—008 | 7/8 |
| 本次续测 | deepseek-v4-flash-0731 | 009—016 | 5/8 |
| 分阶段覆盖 | **混合模型** | 16 个唯一题号 | **12/16（75%）** |

覆盖表的 009 指向本次 DeepSeek 结果，同时原始 Qwen 接口失败记录完整保留。
这不是首轮请求成功率，也不能写成 DeepSeek 或 Qwen 的 12/16 单模型成绩。
两种模型运行的是不同子集，不能据此做公平的模型能力或延迟优劣比较。
001—008 中的 004 工具失败保持不变；本次没有选择性补跑它。

原来的单工具 40/41、多步骤 20/20、原 12 题 12/12 仍是 Qwen 的独立成绩，
没有将 DeepSeek 结果填入这些汇总。新增 16 题现在均有终止观察，但只有 12 题满足状态任务成功条件。

## 原始记录与复现

- 续测：`evals/agent_results/holdout_v3_state_v3_live_1792755980759855100/`。
- 原 Qwen 新题：`evals/agent_results/holdout_v3_state_v3_qwen_1792750085276147200/`。
- 源码、输入、模型及续测题号 manifest、逐题审计和分阶段覆盖表：
  `logs/native_fc_validation/v3_deepseek_followup_1792755978700251100/`。

`audit.json` 保存原 Qwen 文件未变检查、逐题模型归属、失败事件、结果 SHA-256、
字段脱敏与唯一结束事件检查。分阶段覆盖独立存放，没有改写任何原始 summary 或 details。
题目摘要保持
`9a8f5535a909aa493580b952c5431f0b9680b79d4dc5f8e619364bb9bc13a7ea`。

```powershell
uv run --no-sync python -m evals.agent_multistep_eval `
  --mode live --suite holdout_v3 --contract-version 3 `
  --model Qwen-FLASH --model-id deepseek-v4-flash-0731 `
  --task-ids OBJECT-HOLD-009,OBJECT-HOLD-010,OBJECT-HOLD-011,OBJECT-HOLD-012,OBJECT-HOLD-013,OBJECT-HOLD-014,OBJECT-HOLD-015,OBJECT-HOLD-016
```

命令新建独立结果目录；`--model-id` 只覆盖本进程请求，不修改 GUI 配置。
后续再次运行应作为新的观察，不将其悄悄替换进本次结果。
