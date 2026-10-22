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

(4) 会议记录功能需要下载ffmpeg之后才能使用，配置好ffmpeg之后首次运行会自动下载依赖

[FFmpeg配置](https://blog.csdn.net/Natsuago/article/details/143231558)

(5) 联网搜索功能需到.\mcp\websearch\webSearchMCP目录下启动mcp服务器，执行以下命令以启动：
```
$ npm install
$ npm run dev
```
该功能将在本地的3000端口上运行。
