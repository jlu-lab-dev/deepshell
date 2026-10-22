# 人工审批与受控文本创建

本文保留首次五工具 HITL 的实现与验证记录。后续 GUI 已扩展为 41 个工具，
当前策略、启动与验收方式见 [agent_tools_v2.md](../agent_tools_v2.md)；下文的禁用范围及 110 项成绩属于旧配置。

2026-10-21 接入 `create_text_file(filename, content)`，沿用现有
ReAct → Registry → Pydantic → Executor → Trace。正常启动 GUI 时，根据
`config/app.yaml` 在本轮接入时自动启用 4 个只读工具和 1 个受审批的文本创建工具，同时开启脱敏 Trace。
原有删除、覆盖文件、Shell、关机等工具保持禁用。

| UI 中可用的工具 | 参数校验 | 执行方式 |
|---|---|---|
| `get_current_directory` | Pydantic 无参数模型，禁止额外字段 | Executor 直接执行 |
| `get_user_folder_path` | 必填严格字符串、长度限制、禁止额外字段 | Executor 直接执行 |
| `list_running_applications` | Pydantic 无参数模型，禁止额外字段 | Executor 直接执行 |
| `list_applications_by_memory_usage` | 必填严格整数、范围限制、禁止额外字段 | Executor 直接执行 |
| `create_text_file` | 必填文件名与正文、路径及 UTF-8 字节限制、禁止额外字段 | Executor 先登记，再由 Qt 人工审批 |

这些工具通过 AI Agent 对话调用，均由 Registry 注册。原来的其他工具保留底层实现，
并未全部开放，也不应将未注册工具说成已经完成 Pydantic 接入。

## 行为

Executor 首次调用只返回 `PENDING_APPROVAL`，不创建工作区或文件。
Qt 主线程使用非阻塞审批弹窗展示工作目录、文件名、内容 SHA-256 和完整纯文本正文。
Worker 等待用户决议，批准后才消费票据并创建文件，再将结果交回 ReAct 生成最终回答。

票据在内存中绑定原始文件名、内容与工作区，只能消费一次；只接受布尔值 `True` 批准。
修改弹窗预览字典不会改变原申请。拒绝、关窗、过期、超时、停止或关闭功能开关均不能写入。
Worker 最多等待 60 秒，票据有效期为 120 秒；等待结束后会关闭对应弹窗。
切换功能、新建对话及退出应用会取消审批等待。

只允许工作区直接子级的 ASCII `.txt` 文件名，正文为 1～2048 个 UTF-8 字节。
拒绝路径穿越、绝对路径、Windows 设备名、根目录及父目录中的软链接或重解析点。
最终使用 `O_CREAT | O_EXCL` 排他创建，已有文件和同名链接均不覆盖。
这是单用户桌面应用的路径与审批约束，不是多租户操作系统沙箱。

Trace 只保存待审批和执行状态等元数据，不保存审批正文或票据 ID。
新增工具在 `action.args` 与工具记忆中只保存文件名、内容摘要，不保存 `content` 正文。
原有用户消息、可见 Thought 和最终答案继续按原方式保存；脱敏范围不等于整个聊天数据库。
GUI 思考过程、最终答案气泡和原有工作流/记忆持久化保留。

## 接入与验证

使用的 `(2).zip` 与 Downloads 中另外两份同名包摘要一致：
`90ad3eed372df5be56f6adee20387f80546eedd09cab38157357573d6ec5e8c6`。
已有源码先保存到本地 `logs/hitl_review/before/`，仅运行接入脚本预览，再手工合并。
补充修正了新工具被旧白名单提前拒绝、父目录重解析点检查、
弹窗定时器生命周期与审批结束后关闭弹窗的处理。
权限提示词按当前注册的工具生成，避免启用新工具后仍提示完全没有文件创建能力。

| 检查 | 结果 |
|---|---|
| GUI 默认配置、审批、Executor、安全执行、Trace、Agent Eval、表格集成回归 | 110 passed，2 skipped |
| 真实 Qt Worker / Controller / 主线程审批槽 | 批准、拒绝、关窗、超时、停止全部通过 |
| 审批预览 | 完整正文、工作目录、文件名和摘要可见，正文只读 |
| 审批前写入 | 未创建工作区或目标文件 |
| 审批后写入 | 内容与原始申请一致，不能覆盖或重复消费 |
| Windows junction 根目录及父目录 | 实际创建测试 junction，两个入口均被拦截，没有写入目标 |
| GUI 写入开关开启时的旧 30 题 Mock | 30/30，评测仍显式禁用写工具注册 |

2 项跳过是 Windows 当前未开放符号链接创建权限的用例。
Qt 测试使用真实控件和跨线程信号，并注入脚本模型；没有调用真实 Qwen。
未进行真实 Qwen + 用户人工点击的完整窗口验收，也未更新此前 30 题 Qwen 基线成绩。

本地验证材料在 `logs/hitl_validation/`，包括弹窗截图、junction 检查记录和 Mock 输出。
回归命令：

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
uv run --no-sync python -m pytest tests/test_gui_runtime.py tests/test_tool_approval.py tests/test_hitl_executor.py tests/test_safe_tool_executor.py tests/test_agent_trace.py tests/test_agent_eval.py tests/test_table_integration.py -q
```

## GUI 验收

直接启动，无需设置环境变量：

```powershell
cd D:\work\deepshell
uv run --no-sync python singleton_app.py
```

在 GUI 选择已配置的 Qwen 模型和 Agent 模式，然后发送：

1. `在 Agent 工作区创建 hello.txt，内容为 Hello DeepShell。`：审批前无文件，批准后出现。
2. 再次创建同名文件：应失败并保留已有内容。
3. `在 Agent 工作区创建 denied.txt，内容为 test。`：点击拒绝后无文件。
4. 等待超时、关闭审批框或切换功能：无写入，弹窗关闭。
5. 请求写入工作区外的路径、删除文件或执行 Shell：不得执行对应操作。

`config/app.yaml` 的 `agent` 区域保存 GUI 默认值：`approved_write_enabled: true`、
`trace_enabled: true`；相对工作区及日志目录基于项目根目录解析，不受启动终端目录影响。
正常入口在创建 QApplication 前加载配置，并清除遗留的 `offscreen` 设置。
单元测试通过导入模块运行，不自动启用 GUI 配置，不会破坏无窗口测试。

如需默认只读或关闭 Trace，可将对应 YAML 开关设为 `false` 后重启 App。
已有显式环境变量仍可覆盖 YAML：例如 `DEEPSHELL_ENABLE_APPROVED_WRITE=0`。
移除环境变量会恢复 YAML 默认值，不再意味着关闭功能。
实际工作区和日志由 Git 忽略；文件创建依然逐次审批，不会自动批准。
