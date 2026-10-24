# 41 工具分级验收表

2026-10-23。注册、参数、签名和 Executor 安全路径已逐项验证；副作用 handler 全部模拟。
不能将此表理解为全部真实业务或 Qt 操作已验收。真实原生 FC 本轮受 HTTP 403 阻碍。
后续 `qwen3.8-max` 原生 FC 独立复评见 [新模型报告](native_fc_batch_qwen38max.md)，与本表的合同检查分开记录。

| 工具 | Schema/参数/签名 | 审批路径 | Executor（模拟） | 真实业务/Qt |
|---|---|---|---|---|
| `get_current_directory` | 通过 | 只读直接调度 | 通过 | 待分级验收 |
| `get_user_folder_path` | 通过 | 只读直接调度 | 通过 | 待分级验收 |
| `list_running_applications` | 通过 | 只读直接调度 | 通过 | 待分级验收 |
| `list_applications_by_memory_usage` | 通过 | 只读直接调度 | 通过 | 待分级验收 |
| `read_file` | 通过 | 只读直接调度 | 通过 | 待分级验收 |
| `read_table_data` | 通过 | 只读直接调度 | 通过 | 待分级验收 |
| `find_file` | 通过 | 只读直接调度 | 通过 | 待分级验收 |
| `find_files_by_extension` | 通过 | 只读直接调度 | 通过 | 待分级验收 |
| `find_path_by_keywords` | 通过 | 只读直接调度 | 通过 | 待分级验收 |
| `get_contact_email` | 通过 | 只读直接调度 | 通过 | 待分级验收 |
| `open_file` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `create_file` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `write_file` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `rename_file` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `copy_file` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `move_file` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `batch_move_files` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `create_directory` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `delete_file` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `save_text_as_word_doc` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `clean_system_cache` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `batch_rename_files` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `batch_add_prefix_to_filenames` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `open_calculator` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `shutdown_system` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `run_program` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `set_wallpaper` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `open_control_panel` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `open_network_settings` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `open_display_settings` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `open_sound_settings` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `open_bluetooth_settings` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `lock_screen` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `close_application_by_name` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `close_application_by_pid` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `open_task_manager` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `open_browser` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `search_in_browser` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `compose_email` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `generate_report_text` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |
| `create_text_file` | 通过 | 批准/拒绝通过 | 通过 | 待分级验收 |

复现：`uv run --no-sync python -m evals.tool_acceptance`。
本轮机器记录：`evals/agent_results/tool_acceptance_1792739878229035200/matrix.json`。
