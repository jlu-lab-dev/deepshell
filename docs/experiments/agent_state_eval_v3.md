# Agent v3 对象范围契约与状态评测

2026-10-23，实现任务对象范围内的操作前检查、操作后核验、读取预算和写入保护。
v2 的规则、题目及原始结果保留：40/41、20/20、8/12 仍见
[qwen3.8-2.4t-a95b v2 报告](agent_state_eval_qwen38_24t.md)。
v3 使用独立版本号、结果目录和源码快照，没有追溯改判 v2。

## 执行边界

`evals/task_scope.py` 从声明的源对象、目标对象及明确要求的查询推导固定对象集合，
不检查题目 ID，也不根据模型实际调用动态扩大权限。
`sys_agent/object_access.py` 提供可选对象策略，由 `ToolExecutor` 强制执行：

1. Registry 授权与 Pydantic 严格参数校验保持在前。
2. 批次预检查验证路径和任务约束，不消耗读取次数，不调用 handler。
3. 实际执行前再次检查对象、大小、预算与目标是否已存在。
4. 有副作用的操作仍逐次审批；批准后的闭包再次经过 Executor 检查。
5. 受限文件读取直接分派到范围后端，不调用普通的全目录查询 handler。
6. 返回 Observation 前检查结果大小及对象范围，失败时不返回原始内容。

`sandbox_file.py` 的路径校验拒绝路径穿越、同名前缀目录越界、UNC、ADS、设备名和路径别名。
真实路径模式与原文本沙箱共用符号链接/重解析点检查；评测模式只使用相同词法边界，
不访问宿主文件系统。范围后端没有实现受限读取时会失败，不静默回退到普通 handler。

范围查询只查看声明对象的元数据，返回这些对象中的匹配项，不先枚举整个目录再过滤。
因此目标不存在的查找可以返回成功的空列表；目录中无关文件不会进入结果。
查询结果包含 `scoped_lookup=true`，表明它是任务范围查询，不代表整个目录的完整清单。

默认读取上限为每任务 16 次、单文件 16 KiB、单次结果 32 KiB、累计结果 128 KiB，
单次最多 16 个对象。原 Agent 的总工具调用与同工具重复预算仍同时生效。
额外读取统计为开销，不直接判失败；越界、超预算或无效结果仍判契约未通过。

## 参数、审批和最终状态

源路径、目标路径、文件名、内容由任务约束绑定，审批冻结本次参数。
创建、复制、移动、重命名及批量操作维护一致的内存路径与内容；
复制保留源对象，移动/重命名删除旧路径并保持内容，其他对象必须不变。
状态评分从初始状态和声明目标独立构造预期结果，不接受 handler 自称成功作为证明。

创建新文件、复制、移动、重命名不得覆盖现有目标；审批等待期间目标被占用也会拦截。
`write_file`、保存 Word 属于工具本来就声明的覆写能力，只有符合任务目标且批准后才允许覆写。
批量重复源、冲突目标以及已成功操作的重复请求会被拦截，未批准不执行副作用。
这是任务内存状态保护，不是跨进程的持久化幂等实现。

GUI 未自动启用由自然语言推导的对象范围，默认协议仍是 `react_text`。
现有生产 Registry、Pydantic、Executor、审批规则保留；评测器额外注入固定任务范围，
范围约束由同一个 Executor 执行，而不是只在评测后检查。
目前仅实现虚拟文件后端，真实通用文件适配器和真实业务验收尚未完成；
这不是 Shell、进程或整个操作系统的通用沙箱。
非文件工具继续采用模拟执行凭据，报告文本也未进行开放式语义验收。

## 离线验证与新题冻结

完整回归：**504 passed、8 skipped、6 条既有警告**。
新增 v3 的 34 项用例中 33 通过，真实符号链接用例因 Windows 创建权限不足跳过；
重解析点元数据检查通过。其他跳过来自已有条件性用例及默认关闭的联网测试。

测试覆盖合法前置读取、目标不存在、无关读取、目录结果投影、路径穿越、目录前缀越界、
批准后目标占用、重复副作用、批量重复源、错误内容、读取大小/结果/调用预算，
以及不能调用普通目录枚举 handler 的执行入口检查。

脚本模型通过真实 Agent/Executor 链路：

| 题集 | Mock 模拟状态成功 |
|---|---:|
| 原单工具 | 41/41 |
| 原多步骤 | 20/20 |
| 原 12 道新题 | 12/12 |
| v3 新题 | 16/16 |

这 89/89 是确定性基线路径的框架验证，不是 Qwen 成绩。

新增 `evals/agent_state_holdout_v3.jsonl` 的 16 道固定样本，覆盖创建、复制、移动和重命名，
包含嵌套目录、空格、非 ASCII 文件名、不同内容及范围外干扰文件。
题目及摘要在首次 v3 Qwen 请求前冻结，之后未修改：
`9a8f5535a909aa493580b952c5431f0b9680b79d4dc5f8e619364bb9bc13a7ea`。
它们是在已知 v2 问题类型后设计的同域新样本，不是未知真实业务领域的盲测。

## 真实 Qwen 状态：尚未完成

模型仍为 `qwen3.8-2.4t-a95b`，温度 0.3、输出上限 4096、原生 FC 与生产 Prompt 保持不变。
一次接入试跑完成原单工具前 34/41 题，状态通过 33/34、严格通过 32/34，
68 次 HTTP 尝试成功。执行入口审查发现需将受限读取直接路由到范围后端，
因此中止试跑、补充实现及测试后重新冻结整个版本。
中止记录、旧快照和已产生的 Trace 全部保留，未从中挑选成绩拼入正式运行。

最终版本正式复评在第一题首次请求返回 **HTTP 403**，随后停止所有套件：

| 项目 | 当前状态 |
|---|---|
| 原单工具 | 已尝试 1/41，接口拒绝，未完成 |
| 原多步骤 | 未开始 |
| 原 12 题 | 未开始 |
| v3 新 16 题 | 未开始 |

HTTP 403 不能仅凭脱敏记录确定服务商具体拒绝原因。
本轮没有完整真实 Qwen v3 成功率；不能把 Mock 的 12/12、16/16 写成模型能力成绩，
也不能将中止试跑与最终版本混合统计。

## 记录与复现

审计根目录：`logs/native_fc_validation/state_v3_1792747235569127800/`。

- `before/`：本次修改前源码与 v2 题目。
- `frozen/`、`frozen_manifest.json`：中止试跑对应的第一次快照。
- `final_frozen/`、`final_frozen_manifest.json`：最终版本、冻结题目与模型元数据。
- `review_interruption.json`：中止原因、当时汇总及原始文件摘要。
- `runs.json`、`mock_runs.json`：真实与 Mock 结果目录。
- `audit.json`：源码/题集完整性、历史结果摘要及最终运行 Trace 检查。

中止试跑：`evals/agent_results/all_tools_state_v3_qwen_1792748290714806400/`。
正式接口失败：`evals/agent_results/all_tools_state_v3_qwen_1792748706082691900/`。
中止时在途 Trace 可能没有结束事件，按中断保留，不补造完成事件。

```powershell
uv run --no-sync python -m pytest tests/test_agent_state_v3.py tests/test_agent_multistep_eval.py -q
uv run --no-sync python -m evals.agent_multistep_eval --mode mock --suite holdout_v3 --contract-version 3
uv run --no-sync python -m evals.agent_multistep_eval --mode qwen --suite all_tools --contract-version 3
uv run --no-sync python -m evals.agent_multistep_eval --mode qwen --suite multistep --contract-version 3
uv run --no-sync python -m evals.agent_multistep_eval --mode qwen --suite holdout --contract-version 3
uv run --no-sync python -m evals.agent_multistep_eval --mode qwen --suite holdout_v3 --contract-version 3
```

`--contract-version 3` 自动启用状态化评测；默认仍为 v2，可继续使用 `--stateful` 复现其规则。
后续需先恢复接口可用性，在冻结规则下另建正式结果；真实业务、持久化幂等及 MCP 仍是后续阶段。
