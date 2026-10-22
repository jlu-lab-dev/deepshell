"""GUI 启动默认值与真实工具注册/校验链路，不访问在线模型。"""

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from config.config_manager import ConfigManager
from config.gui_runtime import PROJECT_ROOT, configure_gui_runtime
from sys_agent.react_agent import ReActAgent
from sys_agent.tool_registry import SAFE_TOOL_NAMES
from sys_agent.tool_policy import ALL_TOOL_NAMES


def test_gui_defaults_enable_approval_and_trace_without_shell_commands():
    env = {"QT_QPA_PLATFORM": "offscreen"}
    configure_gui_runtime(ConfigManager().app_config, env)
    assert env["DEEPSHELL_ENABLE_APPROVED_WRITE"] == "1"
    assert env["DEEPSHELL_ENABLE_ALL_TOOLS"] == "1"
    assert env["DEEPSHELL_AGENT_TRACE"] == "1"
    assert Path(env["DEEPSHELL_AGENT_WORKSPACE"]) == PROJECT_ROOT / "agent_workspace"
    assert Path(env["DEEPSHELL_AGENT_TRACE_DIR"]) == PROJECT_ROOT / "logs/agent_traces"
    assert "QT_QPA_PLATFORM" not in env


def test_explicit_overrides_and_other_qt_platforms_are_preserved(tmp_path):
    env = {"DEEPSHELL_ENABLE_APPROVED_WRITE": "0", "DEEPSHELL_AGENT_TRACE": "0",
           "DEEPSHELL_AGENT_WORKSPACE": str(tmp_path), "QT_QPA_PLATFORM": "windows"}
    configure_gui_runtime(ConfigManager().app_config, env)
    assert env["DEEPSHELL_ENABLE_APPROVED_WRITE"] == "0"
    assert env["DEEPSHELL_AGENT_TRACE"] == "0"
    assert env["DEEPSHELL_AGENT_WORKSPACE"] == str(tmp_path)
    assert env["QT_QPA_PLATFORM"] == "windows"


def test_gui_settings_can_disable_features_in_yaml():
    env = {}
    configure_gui_runtime({"agent": {"approved_write_enabled": False, "trace_enabled": False}}, env)
    assert env["DEEPSHELL_ENABLE_APPROVED_WRITE"] == "0"
    assert env["DEEPSHELL_AGENT_TRACE"] == "0"
    with pytest.raises(ValueError):
        configure_gui_runtime({"agent": {"approved_write_enabled": "false"}}, {})


def test_standalone_entry_configures_runtime_before_creating_qapplication():
    """执行真实启动块，替身窗口记录初始化顺序，避免加载音频等外围模块。"""
    tree = ast.parse((PROJECT_ROOT / "singleton_app.py").read_text(encoding="utf-8"))
    entry = next(node for node in tree.body if isinstance(node, ast.If)
                 and ast.unparse(node.test) == "__name__ == '__main__'")
    calls = []
    config = {"agent": {"approved_write_enabled": True, "trace_enabled": True}}
    namespace = {
        "ConfigManager": lambda: SimpleNamespace(app_config=config),
        "configure_gui_runtime": lambda value: calls.append(("configure", value)),
        "setup_logging": lambda: calls.append(("logging", None)),
        "QApplication": SimpleNamespace(setHighDpiScaleFactorRoundingPolicy=lambda *_: None),
        "Qt": SimpleNamespace(HighDpiScaleFactorRoundingPolicy=SimpleNamespace(PassThrough=0)),
        "SingleApplication": lambda argv: (calls.append(("application", None)) or SimpleNamespace(is_running=True)),
        "sys": SimpleNamespace(argv=[]),
    }
    exec(compile(ast.Module(body=entry.body, type_ignores=[]), "singleton_app.py", "exec"), namespace)
    assert [name for name, _ in calls] == ["configure", "logging", "application"]


def test_gui_bootstrap_registers_all_validated_tools_and_still_requires_approval(monkeypatch, tmp_path):
    env = {}
    config = {**ConfigManager().app_config, "agent": {
        "approved_write_enabled": True, "trace_enabled": True,
        "all_tools_enabled": True,
        "workspace": str(tmp_path / "workspace"), "trace_directory": str(tmp_path / "traces"),
    }}
    configure_gui_runtime(config, env)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    schemas = [schema for file in (PROJECT_ROOT / "sys_agent/toolkits").glob("*.json")
               for schema in json.loads(file.read_text(encoding="utf-8"))]
    handlers = {name: lambda **kwargs: {"success": True, "message": "mock"} for name in ALL_TOOL_NAMES}
    agent = ReActAgent("fake", schemas, handlers, lambda *_: None, lambda *_: None,
                       lambda *_: None, lambda *_: None, lambda: False,
                       model_manager=SimpleNamespace())
    assert {tool["name"] for tool in agent.tool_schemas} == ALL_TOOL_NAMES | {"create_text_file"}
    assert agent.trace is not None
    assert "{tool_permissions}" not in agent.system_prompt
    for name in SAFE_TOOL_NAMES:
        assert agent.executor.execute(name, {"unexpected": True}).code == "INVALID_ARGS"
    assert agent.executor.execute("list_applications_by_memory_usage", {"memory_threshold_mb": "1024"}).code == "INVALID_ARGS"
    pending = agent.executor.execute("create_text_file", {"filename": "hello.txt", "content": "test"})
    assert pending.code == "PENDING_APPROVAL"
    assert not (tmp_path / "workspace").exists()
    denied = agent.executor.resolve_pending_approval(pending.data["request_id"], False)
    assert denied.code == "APPROVAL_DENIED" and not (tmp_path / "workspace").exists()
