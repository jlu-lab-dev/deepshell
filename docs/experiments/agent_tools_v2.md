# 完整工具接入与 GUI 逐次审批

2026-10-22 已切换至 `qwen3.8-flash` 并完成全工具 84 场景评测，严格规则通过 84/84，
详见 [agent_full_eval_qwen38.md](agent_full_eval_qwen38.md)。旧模型因额度限制仅完成部分有效响应，
原始结果见 [agent_full_eval_v2.md](archive/agent_full_eval_v2.md)。下文保留接入时的回归记录。

2026-10-21 将原有 40 个工具全部接入 Registry → 严格 Pydantic → Executor → Trace，
加上已有的 `create_text_file` 共 41 个。GUI 从 `config/app.yaml` 自动启用，
不再需要在启动前输入环境变量。保留 Thought、Action、Observation、最终答案气泡和历史记录。

## 工具与执行方式

10 个只读工具可直接调用：

- `get_current_directory`、`get_user_folder_path`
- `list_running_applications`、`list_applications_by_memory_usage`
- `read_file`、`read_table_data`
- `find_file`、`find_files_by_extension`、`find_path_by_keywords`
- `get_contact_email`

以下 31 个工具均须在 GUI 中逐次批准：

- 文件：`create_file`、`write_file`、`rename_file`、`copy_file`、`move_file`、
  `batch_move_files`、`create_directory`、`delete_file`、`save_text_as_word_doc`、
  `batch_rename_files`、`batch_add_prefix_to_filenames`、`clean_system_cache`、`create_text_file`
- 程序与系统：`open_file`、`open_calculator`、`shutdown_system`、`run_program`、
  `set_wallpaper`、`open_control_panel`、`open_network_settings`、`open_display_settings`、
  `open_sound_settings`、`open_bluetooth_settings`、`lock_screen`、
  `close_application_by_name`、`close_application_by_pid`、`open_task_manager`
- 浏览器、邮件与报告：`open_browser`、`search_in_browser`、`compose_email`、`generate_report_text`

全部参数模型禁止额外字段和隐式类型转换；批量路径校验数组内的字符串，
表格数据支持嵌套 JSON，拒绝 NaN、Infinity 和任意 Python 对象。
省略可选参数时沿用原函数默认值；正文支持超过旧限制的 256 字符。

## 审批语义与边界

通用弹窗显示工具名、操作影响、完整参数和请求摘要。路径在审批前转换为绝对路径；
票据绑定工具处理函数和参数，GUI 预览副本被修改不会改变执行内容。
批准只能消费一次；拒绝、关窗、超时、停止、重放或关闭对应开关均不会执行。
无审批回调的调用者默认拒绝。工作区文本工具继续使用原来的专用弹窗与排他创建。

`create_text_file` 仍只允许工作区内新建小型 `.txt`，不覆盖已有文件。
原有文件工具则可在用户批准的路径操作，`write_file` 等可覆盖，`delete_file` 永久删除。
这些能力不受专用工作区限制；审批窗会提示影响。
Shell 工具允许执行用户批准的完整命令，不是操作系统级沙箱；其工作目录也在预览时固定。
命令返回实际退出码、标准输出和错误输出；等待超过 60 秒会返回失败，已启动的子进程可能仍在运行。

缓存清理审批展示实际缓存根目录和目标清单，执行时复核路径及文件标识，跳过改变的目标，
不纳入审批后新增的顶层项目，拒绝经过链接或重解析点的目录。
目录内容检查与删除仍是普通文件系统操作，不提供对抗恶意并发修改的原子隔离。

报告工具复用当前 Agent 选择的模型，只有批准后才发起额外调用；不再要求另配 DeepSeek 密钥。
读取表格时将缺失值转换为 JSON `null`。
联系人工具沿用项目中的示例联系人表，没有接入系统通讯录。
邮件工具打开草稿，不会自动发送，也不会自动附加文件，附件需在邮件客户端手动添加。
注册和参数校验通过不意味着系统权限、默认应用、Excel 引擎或模型网络一定可用；
底层失败仍经 Executor 返回。

Trace 继续只记录工具名、参数字段名和状态等元数据，不记录审批全文或票据。
通用审批操作的历史 `action.args` 保存字段名与摘要；用户消息、可见 Thought、
工具返回值和最终回答仍按原聊天逻辑处理，不能把 Trace 脱敏等同于整个聊天数据库脱敏。

## 验证与使用

新增回归覆盖全部 40 个原工具的注册、严格参数校验、直接执行或审批路由，
以及拒绝、过期、并发重放、参数篡改、处理函数替换与路径固定。
真实 Qt Worker / Controller / GUI 审批槽分别验证专用文件和通用命令的
批准、拒绝、关窗、超时和停止。命令与危险工具使用模拟 handler，不执行真实删除或关机；
文件测试仅操作 pytest 临时目录。报告模型也使用替身，不调用在线服务。

回归结果：175 passed，2 skipped。跳过项是当前 Windows 无符号链接创建权限的既有用例；
另有 3 条既有依赖弃用警告。`git diff --check` 通过。

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
uv run --no-sync python -m pytest tests/test_full_tool_integration.py tests/test_gui_runtime.py tests/test_tool_approval.py tests/test_hitl_executor.py tests/test_safe_tool_executor.py tests/test_agent_trace.py tests/test_agent_eval.py tests/test_table_integration.py -q
```

原有 30 题评测显式保留四工具配置与模拟 handler，原 Qwen 27/30 成绩不变，
不作为当前全工具配置的实测成绩。
同时开启两个 GUI 工具环境开关后重跑旧 Mock：30/30，通过结果保存在
`evals/agent_results/archive/cleanup_summaries_20261022.json` 的重复 Mock 摘要；逐题临时输出已清理，评测配置隔离结论保留。

完全退出已有应用（含托盘）后重新启动：

```powershell
uv run --no-sync python singleton_app.py
```

选择已配置模型和 `AI Agent`，可依次验证“当前目录是什么”“打开计算器”以及
“在 Agent 工作区创建 hello.txt，内容为 Hello”。查询直接返回，后两项应出现审批。
用临时文件验证拒绝后文件仍在；无需通过真实关机或删除重要文件验证审批。
尚未运行真实 Qwen 加人工点击的全工具验收。

`agent.all_tools_enabled: true` 启用原有 40 工具，`approved_write_enabled: true`
额外启用工作区文本工具，`trace_enabled: true` 开启 Trace。
若恢复历史四工具配置，将前两个开关都设为 `false` 并重启。
显式环境变量仍能覆盖配置；无需手动设置时直接使用 YAML 默认值。
