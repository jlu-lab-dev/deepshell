## 一、项目介绍

DeepShell 是基于大语言模型（LLM）的操作系统智能体，将LLM与操作系统深度集成，LLM作为操作系统的大脑，用户通过自然语言与操作系统完成交互，LLM分析用户的复杂需求、完成推理、决策、调用操作系统上的工具完成复杂任务。

DeepShell 使用了国内的人工智能引擎，为用户提供了一个多功能的交流平台，支持的在线AI模型为：DeepSeek、阿里的通义千问、讯飞星火，同时支持本地部署Ollama模型。

## 二、使用说明

1、安装

(1) 使用python版本为3.10的环境
```
$ conda create -n deepshell python=3.10
$ conda activate deepshell
```

(2) 安装 uv
```
$ pip install uv
```

(3) 使用 uv 环境（在项目根目录下执行以下命令）
```
$ uv venv .venv
$ uv sync
```

2、运行

(1) 获取api-key ，可以参考链接： 

[DeepSeek API Key](https://platform.deepseek.com/api_keys)

[阿里云百炼 API Key](https://help.aliyun.com/zh/model-studio/developer-reference/get-api-key)

[讯飞星火 API Key](https://xinghuo.xfyun.cn/sparkapi) (点击免费试用、然后点击在线调试，进入调试页面后左边选择`Spark Max`，即可在界面右上方`http服务接口认证信息`看到APIKey)

(2) 重命名`./config/.env.example`为`./config/.env`，将api-key配置到"api_key=" 字段

(3) 运行singleton_app.py (Pycharm解释器：Windows选`.venv/Scripts/python.exe`, Linux系统为`.venv/bin/python`，MacOS为`.venv/bin/python3.10`)

```
$ ./.venv/Scripts/python singleton_app.py
```

正常启动后，在 GUI 选择已配置模型和 `AI Agent` 即可调用原有 40 个工具及
`create_text_file`，全部经过 Registry、严格 Pydantic 校验和 Executor，无需手工设置环境变量。
10 个只读工具直接执行，其余 31 个工具逐次弹窗审批。功能开关、工作区与 Trace
保存在 `config/app.yaml` 的 `agent` 配置中。详情见
[完整工具接入](docs/experiments/agent_tools_v2.md)。

GUI 的 `agent.tool_call_mode` 当前默认 `native_fc`，`react_text` 保留为兼容模式，
可在 `config/app.yaml` 切换后重启。当前模型为 `qwen3.8-max-0902`（配置名称保留 `Qwen-FLASH`）。
协议接入与原始成绩见 [原生 FC 对照报告](docs/experiments/native_fc_comparison.md)，
网络分类、恢复机制与串行实验见 [原生 FC 可靠性排查](docs/experiments/native_fc_reliability.md)。
后续多 Tool Call 顺序调度、41 工具分级验收及 20 题评测见 [批次调度报告](docs/experiments/archive/native_fc_batch_v1.md)。
`qwen3.8-max` 的独立复评见 [新模型结果](docs/experiments/native_fc_batch_qwen38max.md)。
此前 `qwen3.8-2.4t-a95b` 的状态化评测见 [任务状态结果](docs/experiments/agent_state_eval_qwen38_24t.md)。
对象范围、操作前检查及读取预算的 v3 实现与验证见 [v3 契约评测](docs/experiments/agent_state_eval_v3.md)。
当前模型的独立复评及新题中断记录见 [qwen3.8-max-0902 结果](docs/experiments/agent_state_eval_qwen38max0902.md)。
剩余 8 题的 DeepSeek 续测及混合模型覆盖说明见 [续测报告](docs/experiments/archive/agent_state_eval_deepseek_followup.md)。
之后的工具状态语义、读取恢复及真实临时文件/Qt 审批离线验证见 [工具恢复报告](docs/experiments/tool_state_recovery_v1.md)。
此前 DeepSeek 续测的 5/8 保留为历史成绩；529 项通过为离线回归结果。
2026-10-24 的 `qwen3.8-flash` 预检因账号账务错误 `Arrearage` 被拒绝，77 题正式复评未启动，见 [预检记录](docs/experiments/archive/qwen38flash_acceptance_20261024.md)。
随后使用原配置 Key 与 `deepseek-v4.1-flash-1017` 完成修复后 77 题复评：回归 16/16、单工具 39/41、多步骤 20/20，
合计 75/77，均为真实模型 API＋状态化模拟工具；详见 [最新完整复评](docs/experiments/deepseek41flash_acceptance_20261024.md)。

(4) 会议记录功能需要下载ffmpeg之后才能使用，配置好ffmpeg之后首次运行会自动下载依赖

[FFmpeg配置](https://blog.csdn.net/Natsuago/article/details/143231558)

(5) 联网搜索功能需到.\mcp\websearch\webSearchMCP目录下启动mcp服务器，执行以下命令以启动：
```
$ npm install
$ npm run dev
```
该功能将在本地的3000端口上运行。
