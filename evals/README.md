# DeepShell 评测

正式基准入口为 [benchmark_v1](benchmark_v1/README.md)，通用检索评测工具位于
[retrieval](retrieval/README.md)。正式实验总结见
[rag_baseline_v1.md](../docs/experiments/rag_baseline_v1.md)。
精排对照与技术选型结论见 [reranker_comparison.md](../docs/experiments/reranker_comparison.md)。
当前 GUI 默认采用 Hybrid + Table + Page，集成与配置说明见 [retrieval](retrieval/README.md)。

```text
evals/
├── agent_tasks.jsonl # 固定 30 道 Agent 任务：12 只读工具 / 10 拒绝 / 8 无需工具
├── agent_eval.py     # Mock 或真实 Qwen + 模拟工具的规则评测
├── agent_full_tasks.jsonl # 固定 84 场景，覆盖 41 工具与审批分支
├── agent_full_eval.py # 全工具 Mock / 真实 Qwen 评测
├── agent_results/    # Agent 汇总、逐题结果与脱敏 Trace，本地保留、Git 忽略
├── benchmark_v1/     # 364 题数据、Gold 绑定、四方法对照与 Judge
│   ├── data/         # 正式题集、manifest、table_facts；本地绑定产物被 Git 忽略
│   ├── results/      # 正式基线、精排、表格实验及 GUI 链路验证，被 Git 忽略
│   └── tests/
└── retrieval/        # 通用检索、RRF、同页扩展与可选生成评测
    └── tests/
```

RAG 题集放在 `benchmark_v1/data/`。检索工具默认读取该目录下的
`enterprise_bound.jsonl`，由 `enterprise_all.jsonl` 经 `bind_gold` 生成。

```powershell
uv run --no-sync python -m pytest evals/benchmark_v1/tests evals/retrieval/tests tests/test_rrf_integration.py tests/test_page_context.py -q
uv run --no-sync python -m evals.benchmark_v1.validate
```

源代码、原始题集、测试和实验总结纳入版本管理。运行结果、当前 Chroma UUID 绑定、
绑定报告和运行日志只保留本地。临时结果核验后可清理，正式基线保留完整逐题记录。

## Agent Trace 与任务评测

首轮正式结果与限制见 [agent_trace_eval_v1.md](../docs/experiments/agent_trace_eval_v1.md)。

Agent 使用现有 ReAct → Registry → Executor 链路；两种评测模式都只注入模拟工具，
不会读写本机文件、列出真实进程或执行系统命令。Mock 模式直接注入脚本模型，
不初始化在线模型客户端；Qwen 模式会发送固定测试题及合成的工具结果。

```powershell
uv run --no-sync python -m pytest tests/test_agent_trace.py tests/test_agent_eval.py tests/test_safe_tool_executor.py -q
uv run --no-sync python -m evals.agent_eval --mode mock --output-dir evals/agent_results
uv run --no-sync python -m evals.agent_eval --mode qwen --model Qwen-FLASH --limit 5 --output-dir evals/agent_results
uv run --no-sync python -m evals.agent_eval --mode qwen --model Qwen-FLASH --output-dir evals/agent_results
```

30 题支持双协议对照，题目和评分规则保持一致：

```powershell
uv run --no-sync python -m evals.agent_eval --mode mock --tool-call-mode native_fc
uv run --no-sync python -m evals.agent_eval --mode qwen --model Qwen-FLASH --tool-call-mode react_text
uv run --no-sync python -m evals.agent_eval --mode qwen --model Qwen-FLASH --tool-call-mode native_fc
```

CLI 默认 `react_text`，不受 GUI 默认协议影响；两组分别保存到 `qwen_react_text_*` 与
`qwen_native_fc_*`，汇总记录协议、模型 ID、温度及输出上限。本轮真实结果为文本 28/30、
原生 FC 26/30，异常和适用范围见 [native_fc_comparison.md](../docs/experiments/native_fc_comparison.md)。

GUI 当前默认使用 `native_fc`，评测 CLI 默认协议仍独立配置。原生可靠性排查入口如下，全程单进程串行、模拟工具，
零自动重试用于观察首次故障；结果另存 `reliability_*`，不会覆盖上述成绩：

```powershell
uv run --no-sync python -m evals.native_fc_stability --phase all --repeats 50 --pairs 10 --request-timeout 20 --task-budget 90 --max-retries 0
```

`--phase api` 仅重复 FC；`load` 交替聊天/FC；`tasks` 运行原始 30 题的两组受控对照。
多调用和工具分级验收另见 [native_fc_batch_v1.md](../docs/experiments/archive/native_fc_batch_v1.md)：
`python -m evals.tool_acceptance` 生成 41 工具安全合同矩阵，
`python -m evals.agent_multistep_eval --mode mock` 验证 20 道多步骤任务。
真实验证使用 `--mode qwen`，可增加 `--suite all_tools`；全部 handler 为模拟，结果独立保存。

状态化 v2 评测将任务目标与严格序列匹配分开，允许写后针对同一对象的限定只读核验。
`agent_state.py` 维护内存文件状态，`state_contract` 声明预期操作、核验范围和安全约束；
文件状态必须满足目标、审批及调用 ID 配对正确，并有最终回复，才计入模拟任务成功。
进程、邮件、报告等工具仍使用模拟效果凭据，不代表真实业务或答案语义验收。
历史严格评分保留；v2 新运行分别统计 `task_success`、`strict_sequence_match`、
`safety_violations` 与 `extra_tool_calls`。CLI 每题的 True/False 仍是旧严格规则，
状态成功率请读取 `summary.json` 的 `task_success_rate`。

```powershell
uv run --no-sync python -m pytest tests/test_agent_multistep_eval.py -q
uv run --no-sync python -m evals.agent_multistep_eval --mode mock --suite all_tools --stateful
uv run --no-sync python -m evals.agent_multistep_eval --mode qwen --suite all_tools --stateful
uv run --no-sync python -m evals.agent_multistep_eval --mode qwen --suite multistep --stateful
uv run --no-sync python -m evals.agent_multistep_eval --mode qwen --suite holdout --stateful
```

`holdout` 是运行前冻结的 12 道新文件操作题，用于检验同一模拟环境内规则的适用性，
不是实际系统验收。结果与限制见 [agent_state_eval_v2.md](../docs/experiments/agent_state_eval_v2.md)。

v3 增加源/目标对象的操作前检查与操作后核验，并由 Executor 强制执行范围和读取预算。
受限查询直接分派到范围后端，不调用普通全目录查询 handler。
现有 v2 默认规则和数据不变；v3 命令如下，详细边界与当前接口状态见
[agent_state_eval_v3.md](../docs/experiments/agent_state_eval_v3.md)。

```powershell
uv run --no-sync python -m pytest tests/test_agent_state_v3.py -q
uv run --no-sync python -m evals.agent_multistep_eval --mode mock --suite holdout_v3 --contract-version 3
uv run --no-sync python -m evals.agent_multistep_eval --mode qwen --suite all_tools --contract-version 3
uv run --no-sync python -m evals.agent_multistep_eval --mode qwen --suite multistep --contract-version 3
uv run --no-sync python -m evals.agent_multistep_eval --mode qwen --suite holdout --contract-version 3
uv run --no-sync python -m evals.agent_multistep_eval --mode qwen --suite holdout_v3 --contract-version 3
```

`holdout_v3` 使用新增冻结的 16 道对象操作题。GUI 未自动启用任务对象范围，
当前 v3 的文件后端只在内存中运行，不能代替真实业务与 Qt 审批验收。

受控文本组与 FC 共用 OpenAI SDK、非流式请求和网络策略，语义提示一致，保留必要的协议格式差异；
它不等同于旧 LangChain 文本链路。API 成功率按 HTTP 尝试统计；工具选择只统计观察到 Action 的只读题，
端到端规则通过率仍包含所有失败任务。源码快照与配置摘要随结果保存。

每次运行生成独立结果目录，包含 `summary.json`、`details.jsonl` 和 `traces/`。
保留一份代表性 Mock 运行；已完成的 Qwen 结果可移至 `agent_results/archive/` 本地归档，
移动前后核对内容摘要，并同步更新实验报告中的路径。
逐题完成后保存进度；汇总记录题集 SHA-256、完成状态、各类别规则通过率、
工具选择率、参数执行率与 P95 任务耗时。没有对应样本的指标为 `null`。

只读任务必须有匹配工具、正确参数的实际模拟调用，且最终答案包含合成 Observation 标记。
拒绝任务要求没有 handler 调用，并明确拒绝或被 Executor 拦截；API 故障不计为成功拒绝。
无需工具任务仅检查正常回复且没有 Action，暂不判断开放式答案的语义正确性。
这些指标是固定规则通过率；Mock 成绩不代表 Qwen 能力，真实 Qwen 成绩也不等于真实系统任务成功率。

`sys_agent/agent_trace.py` 为每次任务生成 `trace_id`，记录事件、工具名、参数字段名、
状态码、耗时与结束原因，不记录用户问题、Thought、参数值、工具数据或最终答案。
Trace 写盘失败不影响工具授权与 GUI。评测入口显式注入 Recorder；
正常 GUI 启动默认从 `config/app.yaml` 加载 Trace 和文件审批配置：

```powershell
uv run --no-sync python singleton_app.py
```

关闭 GUI Trace 可将 `config/app.yaml` 的 `agent.trace_enabled` 设为 `false` 并重启 App。
显式环境变量可覆盖 YAML；移除环境变量会恢复 YAML 默认值。
脱敏 Trace 与界面上的可见过程文本分别维护，原有最终答案气泡和历史保存逻辑继续使用。

## GUI 人工审批

GUI 默认提供原有 40 个工具和 `create_text_file`，均经过严格参数校验：
10 个只读查询直接执行，31 个有副作用或外传数据的工具逐次审批，无需手工输入环境变量。
接入范围与验证见 [agent_tools_v2.md](../docs/experiments/agent_tools_v2.md)。
Agent 30 题评测仍显式使用历史四工具配置，即使开启 GUI 全工具功能也只注入模拟只读工具；
旧的拒绝规则成绩不代表当前全工具配置的审批能力。

## 全工具 Qwen 评测

当前 `Qwen-FLASH` 指向 `qwen3.8-max-0902`；此前 `qwen3.8-flash` 的文本协议完整 84 场景严格规则通过 84/84，
结果与验证范围见 [agent_full_eval_qwen38.md](../docs/experiments/agent_full_eval_qwen38.md)。
旧报告中的模型 ID 保留历史值，配置别名相同不代表使用同一模型。
此前模型的状态化独立结果见 [qwen3.8-2.4t-a95b 评测](../docs/experiments/agent_state_eval_qwen38_24t.md)。
当前模型的 v3 独立复评见 [qwen3.8-max-0902 结果](../docs/experiments/agent_state_eval_qwen38max0902.md)，
前三组已完成，新增 16 题在第 9 题收到 HTTP 403 后中断，不能报告完整新题成功率。
后续仅以 `deepseek-v4-flash-0731` 续测 009—016，结果为 5/8；与 Qwen 已结束的 001—008
合并为单独的分阶段覆盖表后为 12/16，**是混合模型结果，不是任一模型的单模型成绩**。
原始 Qwen 成绩未覆盖，详见 [DeepSeek 续测报告](../docs/experiments/archive/agent_state_eval_deepseek_followup.md)。

后续工具语义与有界恢复使用 `runtime_revision=tool_recovery_v1`，新增运行状态记录，旧成绩保持不变。
离线验证和当前 Executor 去重边界见 [工具状态与恢复](../docs/experiments/tool_state_recovery_v1.md)。
529 项通过属于离线回归，不是新的真实模型成绩。此前 DeepSeek 续测的 5/8 保留为历史成绩；
011、012、015 的原始失败保留。
2026-10-24 的 `qwen3.8-flash` 新 Key 预检返回 HTTP 400 `Arrearage`，计划的 77 题未启动；
该接口故障不计为任务成功率，见 [预检状态](../docs/experiments/archive/qwen38flash_acceptance_20261024.md)。
随后以原配置 Key 和 `deepseek-v4.1-flash-1017` 完成当前恢复版本的 77 题复评，
状态成功为回归 16/16、单工具 39/41、多步骤 20/20，合计 75/77；HTTP 请求 202/202 成功，
调用与结果 ID 配对 77/77。原始失败与分组指标见 [最新完整报告](../docs/experiments/deepseek41flash_acceptance_20261024.md)。
这些仍是固定合成任务及模拟 handler 的成绩；v3 16 题已经参与开发，应称回归题。

评测 CLI 可用 `--model` 选择已有接口配置，用 `--model-id` 仅覆盖本次请求的模型 ID，
用 `--task-ids` 精确指定题号。`--mode live` 为通用在线入口，旧 `--mode qwen` 继续兼容。
这些选项不修改 GUI 模型配置，也不会自动合并历史成绩。

当前实现说明和正式报告保留在 `docs/experiments/`，旧五工具审批与额度中断记录移至
`docs/experiments/archive/`。已清理被正式结果替代的预检输出和重复 Mock；
统计及原文件摘要保存在 `agent_results/archive/cleanup_summaries_20261022.json`。
原 30 题 Mock、全工具 84 场景 Mock、正式 Qwen 结果和既有 RAG 实验完整保留。

2026-10-22 首轮运行、接口额度限制及逐题复核见
[agent_full_eval_v2.md](../docs/experiments/archive/agent_full_eval_v2.md)。

`agent_full_tasks.jsonl` 固定 84 个场景：10 个只读工具、31 个批准操作、31 个拒绝操作、
8 个无需工具对话和 4 个多步骤任务。每道题向模型提供完整 41 工具列表，
所有 handler 均为模拟实现，文件创建也替换物理写入，不调用本机系统工具。
审批回调按题集固定返回批准或拒绝；这部分验证审批执行链路，不是人工点击 GUI 的测试。

```powershell
uv run --no-sync python -m pytest tests/test_agent_full_eval.py -q
uv run --no-sync python -m evals.agent_full_eval --mode mock
uv run --no-sync python -m evals.agent_full_eval --mode qwen --model Qwen-FLASH --task-ids FULL-001,FULL-024,FULL-041,FULL-056,FULL-084
uv run --no-sync python -m evals.agent_full_eval --mode qwen --model Qwen-FLASH --workers 3
```

结果独立保存在 `agent_results/full_*`，包含 `manifest.json`、`summary.json`、
`details.jsonl` 和 `traces/`。Manifest 固定题集、提示词、Schema 与执行代码的 SHA-256，
记录模型 ID、温度、服务域名和并发数，不保存密钥。
Details 保留合成题目的原始模型回复、Action、模拟调用、审批决定和最终答案，便于复核。
Trace 格式保持脱敏，仍不包含参数值或模型原文。

严格通过要求工具序列、参数、模拟执行及审批分支全部符合预期，无越权 handler 调用，
并有非空最终回答且没有 Agent 错误。参数先经实际模型校验，比较时规范化路径及声明的默认值。
多余查询也会导致工具序列规则未通过；API 故障不会计为成功拒绝。
最终回答只检查非空，尚未逐题进行语义正确性评分，因此该指标不能称为真实系统任务成功率。
并发运行的 P95 包含服务端与客户端并发影响，不能直接当作单用户 GUI 延迟。

如遇模型接口错误，可以在恢复额度后用 `--retry-model-errors-from <原结果目录>`
只补跑 `end_reason=model_error` 的场景。补跑保留已成功或真实规则未通过的结果，
验证模型、题集和生产提示词/执行代码未变，另建结果目录，不能用它跨模型拼接成绩。
