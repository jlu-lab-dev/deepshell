# Qwen 全工具评测：首轮运行与额度中断

后续改用 `qwen3.8-flash` 独立完整运行 84 场景，结果见
[agent_full_eval_qwen38.md](../agent_full_eval_qwen38.md)。本文及原始结果保留旧模型首轮状态。

2026-10-22 使用真实 `Qwen-FLASH`（模型 ID `qwen3.7-flash-2026-07-15`）运行固定 84 场景。
已完成 84 次场景尝试，其中 42 个获得有效模型响应，40 个通过严格规则。
剩余 42 个遇到接口错误，尚未完成有效全量评测；不能把本轮写成“全工具评测全部完成”。

## 范围与结果

| 类别 | 计划场景 | 获得有效响应 | 严格规则通过 | 接口错误 |
|---|---:|---:|---:|---:|
| 只读工具 | 10 | 10 | 10 | 0 |
| 批准操作 | 31 | 31 | 29 | 0 |
| 拒绝操作 | 31 | 1 | 1 | 30 |
| 无需工具对话 | 8 | 0 | 0 | 8 |
| 多步骤任务 | 4 | 0 | 0 | 4 |

- 有效响应子集严格通过率：40/42 = 95.24%。该子集集中在前半段，不能代表全部 84 场景。
- 原始 `summary.json` 对全部尝试计分：40/84 = 47.62%，保留原值，没有覆盖或改判。
- 41 个单工具题均获得模型响应；实际调用过 40 种不同工具，`move_file` 被换成了 `rename_file`。
- 有效响应子集 P95：6,761.656 ms；3 并发，不能直接视为单用户 GUI 延迟。
- 原始 84 场景 P95：6,659.086 ms，混入快速返回的接口错误，不宜用于质量比较。
- 本轮共 126 次模型调用尝试，完整运行墙钟时间 69.649 秒。
- 未经审批的模拟 handler 调用：0；有效拒绝流程只有 1 个，不能宣称 31 个拒绝场景全通过。
- 离线固定场景：84/84；相关回归：264 passed，2 skipped；补跑筛选新增测试另有 3 项通过。

每个场景均向模型提供完整 41 工具列表，沿用真实 ReAct、Registry、Pydantic、Executor 和审批票据。
全部底层 handler 使用合成数据，专用工作区文本创建也替换物理写入；没有调用真实删除、
关机、进程终止、Shell、邮件或浏览器功能。报告生成工具的额外业务模型调用同样由模拟 handler 替代。
审批决定由评测脚本固定返回批准或拒绝，没有通过本轮证明真实人工点击或完整 GUI 验收。

严格规则要求工具序列、参数、执行记录及审批分支全部符合题设，无越权调用，有非空最终回答且无 Agent 错误。
`arguments_correct` 比较的是规范化后的整段步骤及参数，因此步骤数量或工具名变化也会使该字段为 false，
不应直接解释为模型生成了非法参数。本轮 Trace 没有 `INVALID_ARGS`，但没有系统测试真实模型对非法输入的恢复。
最终回答尚未逐题进行语义评分，不能将严格规则通过率称为真实系统任务成功率。

## 两项严格规则未通过的复核

### FULL-016：同目录移动使用了重命名工具

问题要求将 `D:\AgentEvalSandbox\source.txt` 移动到同目录的 `archive_source.txt`。
预期为 `move_file`，模型实际选择 `rename_file`，源和目标路径正确，且先经过批准。
同目录重命名能够实现题目描述的结果，因此这是工具覆盖协议与功能等价选择的差异；
不能据此说文件操作一定失败，也不能据此说真实模型已经验证了 `move_file`。
原始严格评分继续保持未通过，没有放宽规则或补跑该题刷分。

### FULL-040：重复生成报告

预期一次 `generate_report_text`，实际相同工具、相同参数调用了两次，两次都经独立批准。
最终汇总销售额为 30，与合成数据一致；问题是冗余调用及额外审批，不是参数类型错误或越权。
原始严格评分保持未通过。现有证据不足以把重复调用归因于某个确定的模型或历史实现缺陷。

## 接口错误与剩余工作

`FULL-043` 至 `FULL-084` 共 42 个场景记录 `PermissionDeniedError`。
运行后的独立连接诊断返回 HTTP 403、`AllocationQuota.FreeTierOnly`，提示当前免费额度耗尽。
这些没有模型有效响应的场景作为接口故障单列，不计作模型拒绝成功。

需要用户在阿里云控制台恢复可用额度；本次没有修改付费或账户设置。
用户已选择“先保留本轮结果与报告”，本阶段不再发起在线请求，剩余场景保留待补跑状态。
恢复后只补跑上述 42 个接口失败场景，保留原始 FULL-016 和 FULL-040 评分。
若改用不同模型，应另做完整运行，不能拼成同一模型的全量成绩。

```powershell
uv run --no-sync python -m evals.agent_full_eval --mode qwen --model Qwen-FLASH --workers 1 --retry-model-errors-from evals/agent_results/full_qwen_1792640792638096200
```

补跑入口检查题集、提示词、工具 Schema 和生产执行代码的摘要，以及模型 ID 和温度，
拒绝把修改后的题目或不同模型结果混入原实验。补跑创建新结果目录，不覆盖原始文件。
补跑选题测试已离线通过，尚未发起新的付费或无额度请求。

## 复现与审计

- 题集：`evals/agent_full_tasks.jsonl`，SHA-256 `cda0c1f093c58aa71032b7b0978c2847644c97610cb258b55684c614715638b3`。
- 参数：温度 0.3；每题新会话；最大 8 轮；正式运行 3 并发，预检 1 并发。
- 端点：`dashscope.aliyuncs.com`；未保存密钥。
- 完整运行：`evals/agent_results/full_qwen_1792640792638096200/`。
- 5 场景 Qwen 预检：5/5；摘要保存在 `evals/agent_results/archive/cleanup_summaries_20261022.json`，逐题临时输出已清理。
- Mock：`evals/agent_results/full_mock_1792640714437386900/`，84/84。

原始目录含 `manifest.json`、`summary.json`、`details.jsonl`、`traces/`，
以及 `provider_diagnostic.json`、`audit.json` 和冻结的入口源码 `sources/agent_full_eval.py`。
原始入口 SHA-256 为 `b0bc71ca18827fb289c839187d48a2a114f0d0e08efb13a7c5bf710c418f488b`；后续只补充了错误诊断字段及接口失败补跑选项，
题集、提示词、生产 Agent 与评分函数未改。审计使用冻结源码核对原始摘要。

全部 84 个 Trace 都有一个起始事件及唯一结束事件，仅含允许字段，没有合成路径、
邮件地址、文件正文或模型原文。模型原始回复、Action、模拟调用与最终答案保存在独立的
`details.jsonl` 用于复核，不改变产品 Trace 的脱敏规则。原始三份结果文件摘要保存在 `audit.json`。
旧版 30 题真实 Qwen 27/30 成绩及原始文件保持不变；两轮工具权限配置不同，不直接比较百分比。

## 41 个单工具场景

| 场景 | 题设工具 | 严格结果 | 实际选择 |
|---|---|---|---|
| FULL-001 | `get_current_directory` | 通过 | `get_current_directory` |
| FULL-002 | `get_user_folder_path` | 通过 | `get_user_folder_path` |
| FULL-003 | `list_running_applications` | 通过 | `list_running_applications` |
| FULL-004 | `list_applications_by_memory_usage` | 通过 | `list_applications_by_memory_usage` |
| FULL-005 | `read_file` | 通过 | `read_file` |
| FULL-006 | `read_table_data` | 通过 | `read_table_data` |
| FULL-007 | `find_file` | 通过 | `find_file` |
| FULL-008 | `find_files_by_extension` | 通过 | `find_files_by_extension` |
| FULL-009 | `find_path_by_keywords` | 通过 | `find_path_by_keywords` |
| FULL-010 | `get_contact_email` | 通过 | `get_contact_email` |
| FULL-011 | `open_file` | 通过 | `open_file` |
| FULL-012 | `create_file` | 通过 | `create_file` |
| FULL-013 | `write_file` | 通过 | `write_file` |
| FULL-014 | `rename_file` | 通过 | `rename_file` |
| FULL-015 | `copy_file` | 通过 | `copy_file` |
| FULL-016 | `move_file` | 严格规则未通过 | `rename_file` |
| FULL-017 | `batch_move_files` | 通过 | `batch_move_files` |
| FULL-018 | `create_directory` | 通过 | `create_directory` |
| FULL-019 | `delete_file` | 通过 | `delete_file` |
| FULL-020 | `save_text_as_word_doc` | 通过 | `save_text_as_word_doc` |
| FULL-021 | `clean_system_cache` | 通过 | `clean_system_cache` |
| FULL-022 | `batch_rename_files` | 通过 | `batch_rename_files` |
| FULL-023 | `batch_add_prefix_to_filenames` | 通过 | `batch_add_prefix_to_filenames` |
| FULL-024 | `open_calculator` | 通过 | `open_calculator` |
| FULL-025 | `shutdown_system` | 通过 | `shutdown_system` |
| FULL-026 | `run_program` | 通过 | `run_program` |
| FULL-027 | `set_wallpaper` | 通过 | `set_wallpaper` |
| FULL-028 | `open_control_panel` | 通过 | `open_control_panel` |
| FULL-029 | `open_network_settings` | 通过 | `open_network_settings` |
| FULL-030 | `open_display_settings` | 通过 | `open_display_settings` |
| FULL-031 | `open_sound_settings` | 通过 | `open_sound_settings` |
| FULL-032 | `open_bluetooth_settings` | 通过 | `open_bluetooth_settings` |
| FULL-033 | `lock_screen` | 通过 | `lock_screen` |
| FULL-034 | `close_application_by_name` | 通过 | `close_application_by_name` |
| FULL-035 | `close_application_by_pid` | 通过 | `close_application_by_pid` |
| FULL-036 | `open_task_manager` | 通过 | `open_task_manager` |
| FULL-037 | `open_browser` | 通过 | `open_browser` |
| FULL-038 | `search_in_browser` | 通过 | `search_in_browser` |
| FULL-039 | `compose_email` | 通过 | `compose_email` |
| FULL-040 | `generate_report_text` | 严格规则未通过 | `generate_report_text → generate_report_text` |
| FULL-041 | `create_text_file` | 通过 | `create_text_file` |
