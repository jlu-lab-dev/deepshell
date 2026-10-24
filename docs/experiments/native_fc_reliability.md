# 原生 FC 可靠性审查与串行验证

2026-10-22。暂停 MCP，GUI 默认恢复 `react_text`；`native_fc` 保留可选。
本轮确实捕获到连接超时、读取超时和连接异常，并验证了有界恢复；没有证据将首轮全部失败归因于工具决策。
首轮 28/30、26/30 及其 P95 均保留，见 [原始对照](native_fc_comparison.md)。

## 代码审查发现

| 项目 | 原文本链路 | 首轮原生 FC | 本轮处理 |
|---|---|---|---|
| API 客户端 | LangChain ChatOpenAI，流式 | OpenAI SDK，非流式 | 新受控对照统一为 OpenAI SDK、非流式 |
| 网络设置 | 实际 SDK `timeout=None`，`max_retries=2` | 超时 60 秒、零重试 | 对照均为读取 20 秒、连接/池等待最多 5 秒、零重试 |
| 消息历史 | Agent 传入累计上下文，Runnable 又累计一遍 | 每任务一份 assistant/tool 列表 | 文本改为无自动记忆的 `chat_once`；84 场景包装器同步修正 |
| 数据库历史 | 同轮 workflow 和 compact memory 都会注入 | 共用同一加载入口 | 相邻且最终答案一致时优先 compact memory，兼容旧 workflow |
| 工具传递 | 工具定义在 System Prompt | API `tools`，串行工具参数 | 受控组共享语义提示，只保留必要的协议差异 |
| 异常观测 | 只有异常类；SDK 内部尝试不可见 | 首轮没有详细异常信息 | 逐次记录类别、阶段、状态、Request ID、耗时、重试决策 |
| JSON/协议边界 | 文本 Action 解析 | 存在 `1e999` 溢出后才发现非法值的边界 | 提前拒绝；检查消息配对、重复调用 ID、截断输出及 Schema required |

本地核对版本：OpenAI SDK 1.72.0、HTTPX 0.28.1、langchain-community 0.3.20。
文本无显式超时是检查实际构造出的 SDK 客户端得到的结果，不能把“文本首轮没报错”解读为相同网络条件下更可靠。
普通聊天/RAG 的 ModelManager 历史机制未改；Agent 自己管理上下文，因此使用独立的无自动记忆入口。

受控文本组与生产 LangChain 文本链路不同。GUI 文本仍使用 LangChain 的既有网络设置；本轮没有扩展为全应用网络层重构。
思考模式未显式配置，两组均省略该参数，沿用服务商默认行为；不能据此断言两种协议触发完全相同的服务端处理路径。

## 原生请求分类与恢复

`NativeFCSession` 继续直接调用 OpenAI 兼容 API，不引入第二套模型配置。
`config/app.yaml` 的 `agent.native_fc_network` 当前为：

```yaml
request_timeout: 20.0
task_budget: 90.0
max_retries: 1
backoff_base: 0.5
```

SDK 内部重试固定为零，由应用层记录每次实际尝试；注入真实 SDK 客户端也必须关闭内部重试。
仅连接/超时、408、409、429、5xx 可以按预算重试，最多一次；尊重 `x-should-retry=false` 和有效 `Retry-After`，
没有有效服务端等待时间时使用带抖动的指数退避。等待超过剩余预算则停止，不提前重发。
本地参数/Schema、401/403 等不可恢复 HTTP 错误以及协议错误不重试。
异常类别遵循 [OpenAI SDK 文档](https://developers.openai.com/api/reference/python)，
退避与预算原则参考 [限流文档](https://developers.openai.com/api/docs/guides/rate-limits)；Qwen 实际行为以本次记录为准。

Trace 增加具名的 `model_request` 字段，保留 HTTP 尝试、异常类型、底层超时阶段、状态码、Request ID、
请求字节数、消息数、Schema 数及大小、finish_reason 和重试是否安排/停止原因。
JSON 参数错误与消息协议错误有独立协议代码。连接失败尚未收到 HTTP 响应时没有 Request ID，不伪造该字段。
不记录密钥、URL 凭据、用户问题、模型正文、隐藏推理、参数值或工具数据；GUI 错误也不再直接拼接服务端异常正文。

恢复只重发当前模型请求，不重启 Agent，不重新申请审批或重放 handler。
已确认工具结果可再次交给模型；工具异常或结果不确定时仍按 Executor 终止，不能自动重新执行有副作用的操作。
取消会中断退避并阻止后续请求，收到回复后也会再次检查取消和预算，随后才允许分派工具。

预算限制后续请求与重试的调度；HTTPX 的超时是网络阶段/读取等待限制，**不是同步调用的硬墙钟截止时间**。
正在进行的同步 HTTP 请求不能保证瞬时取消，必须等待返回或网络超时；不能宣称所有任务必定在 90 秒内结束。

## 零重试串行实验

所有网络请求单进程串行执行。模型 `qwen3.7-flash`、服务 `dashscope.aliyuncs.com`、温度 0.3、输出上限 4096，
总调度预算 90 秒；SDK 和应用自动重试均为零。A/B 不执行工具，仅检查模型响应；C/D 复用原始 30 题及四个模拟只读工具。
文本完整组结束后才开始原生完整组，没有两组并发。

| 阶段 | API 成功/尝试 | 本次输出/任务规则通过 | P95（含失败） |
|---|---:|---:|---:|
| A：相同单工具 FC 请求 50 次 | 47/50 | 47/50，单次输出检查 | 5,027.849 ms |
| B：交替普通聊天，10 次 | 7/10 | 7/10，非空回复检查 | 20,072.470 ms |
| B：交替 FC，10 次 | 8/10 | 8/10，单次输出检查 | 5,030.564 ms |
| C/D：受控文本 30 题 | 41/43 | 25/30，Agent 规则 | 7,614.774 ms |
| C/D：受控原生 30 题 | 38/42 | 26/30，Agent 规则 | 8,966.582 ms |

A/B 不是完整 Agent 任务成功率；结果 JSON 使用统一规则统计字段，解释时必须结合阶段。
API 成功表示服务返回了响应，协议有效性与答案规则另计；多轮任务可能产生不止一次 HTTP 尝试。
工具选择统计仅针对已观察到 Action 的只读题：文本 11/11、原生 12/12。
文本另有一题在产生决策前请求失败，仍计入完整任务分母，不能将条件性 100% 当作全题成功率。
无需工具题未进行开放式语义审核。

共捕获 14 次 HTTP 尝试失败，均有明确分类：10 次 ConnectTimeout、3 次 ReadTimeout、1 次 APIConnectionError。
其中 A 的 50 个请求体大小均为 911 字节、消息数固定为 2，排除了该重复实验内消息累积的解释。
C/D 的消息数范围为 2–4，未出现未配对工具消息或异常历史膨胀；有效 HTTP 返回均获得 Request ID。

文本任务失败：009（连接异常）、025（连接超时），以及 013/018/022（发生额外只读调用，严格拒绝规则不通过）。
原生失败：018（读取超时）、021/022/025（连接超时）。这些失败没有危险 handler 执行。
新两组均出现网络故障，不能将网络可靠性问题简单归因于 FC 参数或工具选择。
本次未发现 HTTP 4xx/5xx、Schema 或协议异常；相应分类与恢复路径由离线故障注入覆盖。

这些记录明确定位到本轮连接建立/读取等待阶段，尚不能区分具体的 DNS、TCP、TLS、运营商链路或服务端排队原因。
没有配置 HTTP/HTTPS/ALL_PROXY 环境变量。不能从这些新记录倒推首轮 4 次异常的唯一根因；首轮缺失的异常信息无法补回。

## 独立恢复验证

随后使用相同固定 FC 请求再运行 50 次，唯一恢复策略变化是 `max_retries=1`。
本次共有 52 次 HTTP 尝试：50 次成功，2 次连接超时；两次均按退避策略重试一次后成功。
50 个单次请求流程最终通过，P95 为 4,770.154 ms；HTTP 尝试成功率仍是 50/52，不能写成 API 永不失败。
本轮与前一轮处于不同时间窗口，不能把两个样本的差值全部解释成重试的因果收益；两条失败→重试→成功轨迹直接验证了恢复路径。
没有为提高分数改题、改温度、换模型或反复重跑 30 题，也没有合并任何旧成绩。

## 回归与 Qt

| 检查 | 结果 |
|---|---:|
| 完整离线 `pytest tests -q` | 415 passed，7 skipped |
| 真实 Qwen + Qt 查询、批准、拒绝、取消 | 4/4 |

末尾将重试计数限定为实际发起的第二次及以后尝试（取消时不把仅安排的重试计入），额外定向回归 147 项通过。

故障注入覆盖认证/限流/5xx、四类超时阶段、连接失败、次数及时间预算、Retry-After、取消、截断响应、
非有限参数、孤立/重复工具 ID、Trace 脱敏，以及工具已执行后模型请求重试不重复 handler。
同时验证最终答案气泡、workflow/memory 持久化、真实 AgentHistoryWidget 展开及加载历史只注入一次。
历史回放验证为离线真实 Qt 控件测试，不把它写成真实 Qwen 对话语义评测。

联网 Qt 使用真实 Controller/Worker、MainWin 审批槽和按钮；查询数据为合成数据，批准创建仅写 pytest 临时目录。
拒绝和取消没有文件写入，也没有真实删除、Shell、关机或进程终止。按钮由测试程序点击，不代替完整窗口的人工验收。
7 项跳过包括 4 个默认关闭的联网测试及 3 个既有条件性用例；6 个既有依赖/环境警告仍在。

## 结果、审计和复现

- 零重试全阶段：`evals/agent_results/reliability_1792669246390260500/`。
- 单次重试验证：`evals/agent_results/reliability_1792669834026739900/`。
- 新 Qt 记录：`logs/native_fc_validation/reliability_qt_1792669989337692900/`，没有覆盖旧 Qt 结果。
- 脱敏、消息配对、请求分层统计、源文件和历史结果摘要审计：`logs/native_fc_validation/reliability_audit.json`。

两个结果目录均保存 manifest、当时源码快照、summary、details、Trace。
零重试实验后只补充历史去重、协议细分、停止重试原因及统计输出，没有修改请求提示或模型参数；具体源码版本以各自快照为准。
后续对指标输出与 84 题包装器的改动由最终离线回归覆盖，没有将新版本测试冒充成旧源码实验。
原始 28/30、26/30 目录及旧 Trace、摘要保持完整。

```powershell
# 独立的串行排查，零自动重试
uv run --no-sync python -m evals.native_fc_stability --phase all --repeats 50 --pairs 10 --max-retries 0

# 独立恢复样本，不合并成绩
uv run --no-sync python -m evals.native_fc_stability --phase api --repeats 50 --max-retries 1

# 离线回归
$env:QT_QPA_PLATFORM = "offscreen"
Remove-Item Env:DEEPSHELL_TEST_LIVE_QWEN -ErrorAction SilentlyContinue
uv run --no-sync python -m pytest tests -q

# 显式联网验证，结果保存到新的目录
$env:DEEPSHELL_TEST_LIVE_QWEN = "1"
uv run --no-sync python -m pytest tests/test_native_fc_live.py -q
```

当前保留原生 FC 的分类、恢复和可复现实验；继续以 `react_text` 为 GUI 默认模式，MCP 仍暂停。
真实环境中仍观察到连接/读取故障，不能宣称外部服务稳定性已彻底解决，也不能据此宣称两种协议的决策能力优劣。
