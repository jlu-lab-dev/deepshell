# deepseek-v4.1-flash-1017：修复后原生 FC 77 题复评

2026-10-24，按用户要求恢复使用项目原来配置的 Key，沿用百炼
`dashscope.aliyuncs.com` 的 OpenAI 兼容接口，实际模型为 `deepseek-v4.1-flash-1017`。
普通回答及原生工具调用预检通过后，完成全部 77 题，状态任务成功 **75/77（97.40%）**。
此前新 Key 的 Qwen 预检账务错误独立保留，不能据此认为那个账号已恢复可用。

## 同一模型、版本与执行条件

- 串行执行 v3 回归 16 题、单工具 41 题、多步骤 20 题，每题只保留首次正式任务记录。
- 全程使用同一模型 ID、温度 0.3、输出上限 4096、原生 FC、v3 契约及 `tool_recovery_v1` 运行时。
- 请求超时 20 秒、单任务模型请求预算 90 秒、应用重试上限 1；SDK 隐式重试关闭。
- 工具、Prompt、题集、评分、安全策略及生产运行源码在运行前冻结摘要，结束后核对一致。
  没有为提高成绩修改题目、评分或重新运行失败任务。
- `Qwen-FLASH` 仅是复用配置地址和凭据的别名；summary 与逐题记录均保存实际 DeepSeek 模型 ID。
  没有修改 Key、`.env` 或 GUI 模型配置。GUI 原生 `native_fc` 默认开关保持启用，模型仍按其已有配置选择。

调用真实模型、Registry、Pydantic、Executor、审批票据和 Trace；所有 handler 与审批决定均为模拟实现。
文件工具维护内存状态，非文件工具主要检查参数和模拟效果凭据。
这不是真实系统操作、完整业务结果、人工 Qt 验收或开放式答案语义正确率。

## 正式结果

| 指标 | v3 回归题 | 单工具 | 多步骤 |
|---|---:|---:|---:|
| 已完成 / 计划 | 16/16 | 41/41 | 20/20 |
| 模拟状态任务成功 | **16/16（100%）** | **39/41（95.12%）** | **20/20（100%）** |
| 严格执行序列与参数匹配 | 0/16 | 33/41 | 18/20 |
| 调用与结果 ID 配对完整 | 16/16 | 41/41 | 20/20 |
| HTTP 尝试成功 | 63/63 | 90/90 | 49/49 |
| 未授权副作用执行记录 | 0 | 0 | 0 |
| 对象/任务契约拒绝记录 | 0 | 1 | 0 |
| 平均实际 handler 调用 | 4.562 | 1.317 | 2.000 |
| 超出参考数量的实际调用 | 57 | 13 | 0 |
| 任务 P95（毫秒，含未通过题） | 8,119.241 | 4,727.751 | 5,476.795 |

正式 202 次 HTTP 尝试全部成功，没有应用层实际重试或终止性模型调用异常。
另外 3 次成功的预检请求独立存放，没有混入上述指标。
77 题均观察到工具决策，全部调用与结果 ID 完整配对；实际收到 38 次双工具响应，均由本地顺序调度。
76 个 Trace 以 `completed` 结束，1 个以 `tool_error` 结束。

状态成功与严格匹配分别统计。允许的对象核验会增加调用，但不会单独导致状态任务失败。
多步骤任务的参考调用数量不完全相同，额外调用按每题实际数量超过参考数量的部分统计，不能由平均值直接推断。
P95 是本轮网络环境下的任务耗时，不是 CPU 延迟或 GUI 性能保证。

## 两道未通过任务

| 题号 | 观察结果 | 保留的判定 |
|---|---|---|
| FULL-008 | 两次 `find_files_by_extension` 均成功，之后有最终回答；无范围违规，但目标契约未满足 | 状态任务失败 |
| FULL-017 | `find_file`、`find_path_by_keywords` 查询成功；随后 `create_directory` 被 `OBJECT_OUT_OF_SCOPE` 拦截，没有审批或目录 handler 调用，没有最终回答 | 状态任务失败，范围拦截有效 |

FULL-008 未满足冻结的主查询凭据要求。脱敏记录不保留参数及回答正文，不能逐项确定参数差异，
也不能仅凭两次查询成功就认定语义任务完成；没有人工改判或现场修改查询契约。
FULL-017 的 1 条契约拒绝不等于已经发生越权执行：目录操作没有进入 handler。
所以“未授权副作用执行记录为 0”和“契约拒绝记录为 1”并不矛盾。
这些结论都限定于模拟环境，不构成生产全部权限边界的证明。

## 读取与恢复覆盖

16 道 v3 题中，历史上未通过的 004、011、012、015 在本轮新模型和修复后运行时组合下均通过。
本轮实际产生 17 次 `NOT_FOUND`，Agent 能处理对象不存在的状态并完成相应任务。
共 62 项副作用获得脚本审批并记录为 `SUCCEEDED`；没有出现 `READ_FAILED`、`UNKNOWN`
或 `DUPLICATE_SIDE_EFFECT`，因此不能声称这次真实模型运行覆盖了所有故障恢复和去重分支。
这些分支的覆盖仍来自 [工具状态与恢复的离线验证](tool_state_recovery_v1.md)。

与旧 DeepSeek 5/8 相比，本轮模型和运行时均不同，不能把改善单独归因于恢复修复或模型更强。
16 题已经参与过诊断与开发，属于回归集，不是完全未接触的新留出集。
旧 Qwen、旧 DeepSeek 及混合模型 12/16 保留，没有替换或合并进本次 75/77。

## 汇总中断与记录完整性

首题完成并落盘后，验收包装脚本因 Windows 路径分隔符与统计查找键不一致触发 `KeyError`。
该问题发生在读取题集摘要的汇总步骤，模型及工具执行均正常。
仅在汇总器中统一 manifest 的查找键，然后从第 2 题继续；没有重新执行第 1 题或重复预检。
首题原始 JSONL 行已逐字节核对摘要相同。
所以本轮是一次正式结果集的串行续跑，不能说成全程没有任何脚本中断。

生产运行时、任务执行器、评分及题目均未改动，未重复已经通过的 529 项完整离线回归。
`unexpected_driver_error.json`、`aggregation_fix.json` 及续跑脚本保留汇总故障与修正依据。

## 结果与复现

- v3 回归：`evals/agent_results/holdout_v3_state_v3_deepseek41flash_recovery_1792816464163612800/`。
- 单工具：`evals/agent_results/all_tools_state_v3_deepseek41flash_recovery_1792816672501318900/`。
- 多步骤：`evals/agent_results/multistep_state_v3_deepseek41flash_recovery_1792816788355904500/`。
- 预检、冻结 manifest、源码与题集快照、逐题失败项、结果文件摘要及字段白名单审计：
  `logs/native_fc_validation/deepseek41flash_acceptance_20261024_1792816448010555100/`。

77 个正式 Trace 均有起始及唯一结束事件，字段白名单与脱敏检查通过；
1,233 个历史结果文件和冻结的源码、题集、配置摘要核对未变。没有保存 Key、参数值或模型回答正文。
调用 ID 配对是在执行时对原生消息列表进行比对，脱敏报告不保存完整消息体。

```powershell
uv run --no-sync python -m evals.agent_multistep_eval --mode live --suite holdout_v3 --contract-version 3 --model Qwen-FLASH --model-id deepseek-v4.1-flash-1017
uv run --no-sync python -m evals.agent_multistep_eval --mode live --suite all_tools --contract-version 3 --model Qwen-FLASH --model-id deepseek-v4.1-flash-1017
uv run --no-sync python -m evals.agent_multistep_eval --mode live --suite multistep --contract-version 3 --model Qwen-FLASH --model-id deepseek-v4.1-flash-1017
```

命令会新建结果目录，读取当时配置的凭据；复现时还须核对本轮 manifest 中的全部摘要和参数。
这些结果可以表述为“同一 DeepSeek 模型、修复后运行时、真实 API＋状态化模拟工具的固定 77 场景中通过 75 场景”。
不应写成真实系统业务成功率 97.40%、全部工具真实业务验收完成或未见新题泛化率 100%。
