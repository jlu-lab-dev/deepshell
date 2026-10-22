"""将 GUI 的持久配置应用到本进程；评测入口不加载这些 GUI 默认值。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import MutableMapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def configure_gui_runtime(app_config: dict, environ: MutableMapping[str, str] | None = None) -> None:
    """正常窗口启动前调用，已有显式环境变量覆盖 YAML 配置。"""
    env = os.environ if environ is None else environ
    settings = app_config.get("agent", {})
    for key, variable in (
        ("approved_write_enabled", "DEEPSHELL_ENABLE_APPROVED_WRITE"),
        ("all_tools_enabled", "DEEPSHELL_ENABLE_ALL_TOOLS"),
        ("trace_enabled", "DEEPSHELL_AGENT_TRACE"),
    ):
        value = settings.get(key, False)
        if not isinstance(value, bool):
            raise ValueError(f"app.agent.{key} 必须是布尔值")
        env.setdefault(variable, "1" if value else "0")

    for key, variable, default in (
        ("workspace", "DEEPSHELL_AGENT_WORKSPACE", "agent_workspace"),
        ("trace_directory", "DEEPSHELL_AGENT_TRACE_DIR", "logs/agent_traces"),
    ):
        configured = Path(settings.get(key, default)).expanduser()
        if not configured.is_absolute():
            configured = PROJECT_ROOT / configured
        env.setdefault(variable, str(configured.absolute()))

    # 此函数只用于正常 GUI 入口，移除上次测试遗留的无窗口设置。
    if env.get("QT_QPA_PLATFORM") == "offscreen":
        env.pop("QT_QPA_PLATFORM")
