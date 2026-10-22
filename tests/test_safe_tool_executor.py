"""测试 DeepShell 安全工具执行层：所有测试使用假的 handler，不读取或修改真实系统。"""

import json
from pathlib import Path

import pytest

from sys_agent.tool_executor import ToolExecutor
from sys_agent.tool_registry import ToolRegistry, SAFE_TOOL_NAMES


ROOT = Path(__file__).resolve().parents[1]


def make_executor():
    schemas = []
    for path in (ROOT / "sys_agent" / "toolkits").glob("*.json"):
        schemas += json.loads(path.read_text(encoding="utf-8"))
    calls = []

    def fake(**kwargs):
        calls.append(kwargs)
        return {"success": True, "message": "模拟成功", "echo": kwargs}

    # 即使危险工具在 FUNCTION_MAP 里有处理函数，Registry 也必须拒绝。
    handlers = {schema["name"]: fake for schema in schemas}
    return ToolExecutor(ToolRegistry.from_existing(schemas, handlers)), calls


def test_only_four_read_only_tools_shown_to_model():
    executor, _ = make_executor()
    names = {x["name"] for x in executor.registry.get_tool_schemas()}
    assert names == SAFE_TOOL_NAMES
    assert "delete_file" not in names
    assert "run_program" not in names


@pytest.mark.parametrize("name", ["run_program", "shutdown_system", "delete_file", "clean_system_cache"])
def test_dangerous_functions_not_invoked(name):
    executor, calls = make_executor()
    result = executor.execute(name, {"command": "echo dangerous"})
    assert result.code == "PERMISSION_DENIED"
    assert not calls


def test_unknown_tool_is_rejected():
    executor, calls = make_executor()
    result = executor.execute("no_such_tool", {})
    assert result.code == "UNKNOWN_TOOL" and result.retryable
    assert not calls


def test_invalid_argument_type_no_implicit_coercion():
    executor, calls = make_executor()
    result = executor.execute("list_applications_by_memory_usage", {"memory_threshold_mb": "1024"})
    assert result.code == "INVALID_ARGS"
    assert not calls


def test_extra_argument_rejected():
    executor, calls = make_executor()
    result = executor.execute("get_current_directory", {"command": "anything"})
    assert result.code == "INVALID_ARGS"
    assert not calls


def test_missing_required_parameter_rejected():
    executor, calls = make_executor()
    result = executor.execute("get_user_folder_path", {})
    assert result.code == "INVALID_ARGS"
    assert not calls


@pytest.mark.parametrize("arguments", ["{}", [], None])
def test_non_object_args_rejected(arguments):
    executor, calls = make_executor()
    result = executor.execute("get_current_directory", arguments)
    assert result.code == "INVALID_ARGS"
    assert not calls


def test_valid_tool_executes_once():
    executor, calls = make_executor()
    result = executor.execute("list_applications_by_memory_usage", {"memory_threshold_mb": 1024})
    assert result.success is True and result.code == "SUCCESS"
    assert calls == [{"memory_threshold_mb": 1024}]
    assert result.data["echo"] == {"memory_threshold_mb": 1024}


def test_malformed_result_rejected():
    executor, _ = make_executor()
    tool = executor.registry.get("get_current_directory")
    from sys_agent.tool_registry import RegisteredTool
    registry = executor.registry
    registry._tools["get_current_directory"] = RegisteredTool(tool.name, tool.schema, lambda: "bad", tool.args_model)
    result = executor.execute("get_current_directory", {})
    assert result.code == "TOOL_ERROR"


def test_handler_exception_no_crash():
    executor, _ = make_executor()
    from sys_agent.tool_registry import RegisteredTool
    tool = executor.registry.get("get_current_directory")

    def broken():
        raise RuntimeError("cannot read")

    executor.registry._tools["get_current_directory"] = RegisteredTool(tool.name, tool.schema, broken, tool.args_model)
    result = executor.execute("get_current_directory", {})
    assert result.code == "TOOL_ERROR"
    assert not result.success


def test_declared_failure_normalized():
    executor, _ = make_executor()
    from sys_agent.tool_registry import RegisteredTool
    tool = executor.registry.get("get_current_directory")
    executor.registry._tools["get_current_directory"] = RegisteredTool(
        tool.name, tool.schema, lambda: {"success": False, "message": "无权限"}, tool.args_model
    )
    result = executor.execute("get_current_directory", {})
    assert result.code == "TOOL_FAILED" and result.message == "无权限"


def test_every_disabled_tool_is_rejected_without_handler_call():
    executor, calls = make_executor()
    for name in executor.registry.known_names - SAFE_TOOL_NAMES:
        assert executor.execute(name, {}).code == "PERMISSION_DENIED"
    assert not calls


@pytest.mark.parametrize("threshold", [True, 1024.0, 0, -1, 1_000_001])
def test_threshold_rejects_boolean_float_and_out_of_range_values(threshold):
    executor, calls = make_executor()
    assert executor.execute("list_applications_by_memory_usage", {"memory_threshold_mb": threshold}).code == "INVALID_ARGS"
    assert not calls


def test_executor_checks_allowlist_even_for_direct_registry_construction():
    from sys_agent.tool_registry import RegisteredTool
    executor, calls = make_executor()
    safe = executor.registry.get("get_current_directory")
    disabled = RegisteredTool("run_program", {}, safe.handler, safe.args_model)
    executor = ToolExecutor(ToolRegistry({"run_program": disabled}, frozenset({"run_program"})))
    assert executor.execute("run_program", {}).code == "PERMISSION_DENIED"
    assert not calls


@pytest.mark.parametrize("value", [
    object(), float("nan"), float("inf"), float("-inf"),
    {"rows": [{"value": float("nan")}]},
    {"rows": [{"value": float("inf")}]},
    {"rows": [{"value": float("-inf")}]},
])
def test_unserializable_or_nonfinite_tool_data_becomes_error(value):
    from sys_agent.tool_registry import RegisteredTool
    executor, _ = make_executor()
    tool = executor.registry.get("get_current_directory")
    executor.registry._tools[tool.name] = RegisteredTool(
        tool.name, tool.schema, lambda: {"success": True, "message": "done", "value": value}, tool.args_model)
    assert executor.execute(tool.name, {}).code == "TOOL_ERROR"


def test_finite_nested_tool_data_remains_serializable():
    from sys_agent.tool_registry import RegisteredTool
    executor, _ = make_executor()
    tool = executor.registry.get("get_current_directory")
    value = {"rows": [{"memory_mb": 1024.5, "optional": None}], "count": 1}
    executor.registry._tools[tool.name] = RegisteredTool(
        tool.name, tool.schema,
        lambda: {"success": True, "message": "done", "value": value}, tool.args_model)
    result = executor.execute(tool.name, {})
    assert result.success and result.code == "SUCCESS"
    assert result.data["value"] == value
    assert json.loads(result.model_dump_json())["data"]["value"] == value


def make_agent(monkeypatch, responses):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from sys_agent import react_agent

    executor, calls = make_executor()
    model = SimpleNamespace(chat=Mock(side_effect=responses))
    monkeypatch.setattr(react_agent, "ModelManager", lambda: model)
    monkeypatch.setattr(react_agent, "ConfigManager", lambda: SimpleNamespace(
        get_assistant_config=lambda name: {"prompt_template": "工具：{tool_schemas}"}))
    observed = {"steps": [], "observations": [], "finals": [], "errors": [], "traces": []}
    # 传入全部40个工具，验证 Agent 自身会过滤，而不是依赖调用者事先过滤。
    schemas = [schema for path in (ROOT / "sys_agent/toolkits").glob("*.json")
               for schema in json.loads(path.read_text(encoding="utf-8"))]
    def handler(**kwargs):
        calls.append(kwargs)
        return {"success": True, "message": "模拟成功", "path": "fake/path"}
    agent = react_agent.ReActAgent(
        model_name="fake", tool_schemas=schemas, function_map={s["name"]: handler for s in schemas},
        step_cb=lambda sid, text: observed["steps"].append((sid, text)),
        obs_cb=lambda sid, success, message: observed["observations"].append((sid, success, message)),
        final_cb=observed["finals"].append, error_cb=observed["errors"].append,
        stop_flag=lambda: False, thought_chain_collector=observed["traces"].append)
    return agent, model, calls, observed


def test_action_decoder_handles_nested_json_and_following_text():
    from sys_agent.react_agent import _extract_action
    expected = {"tool": "example", "args": {"nested": {"values": [1, 2]}, "text": "a } brace"}}
    response = "Thought: test\nAction: " + json.dumps(expected) + "\nObservation: must not be parsed"
    assert _extract_action(response) == expected
    assert _extract_action('Action: {"tool": "get_current_directory", "args":') is None


def test_agent_prompt_exposes_only_safe_tool_schemas(monkeypatch):
    agent, _, calls, _ = make_agent(monkeypatch, [])
    assert {s["name"] for s in agent.tool_schemas} == SAFE_TOOL_NAMES
    assert "run_program" not in agent.system_prompt
    assert not calls


def test_agent_recovers_from_parse_error_then_executes_once(monkeypatch):
    agent, model, calls, observed = make_agent(monkeypatch, [
        'Thought: test\nAction: {"tool":"get_current_directory","args":',
        'Action: {"tool":"get_current_directory","args":{}}',
        'Final Answer: 已完成'])
    agent.run("模拟问题")
    assert calls == [{}]
    assert model.chat.call_count == 3
    assert observed["finals"] == ["已完成"] and not observed["errors"]
    assert any("PARSE_ERROR" in message for message in model.chat.call_args_list[1].kwargs["messages"])
    successful = [t for t in observed["traces"] if t.get("tool_result", {}).get("success")]
    assert successful[0]["tool_result"]["data"]["path"] == "fake/path"


def test_agent_stops_after_two_parse_errors(monkeypatch):
    agent, model, calls, observed = make_agent(monkeypatch, ['Action: {', 'Action: {'])
    agent.run("模拟问题")
    assert model.chat.call_count == 2 and not calls
    assert observed["errors"] and not observed["finals"]


def test_agent_recovers_from_invalid_args(monkeypatch):
    agent, model, calls, observed = make_agent(monkeypatch, [
        'Action: {"tool":"list_applications_by_memory_usage","args":{"memory_threshold_mb":"1024"}}',
        'Action: {"tool":"list_applications_by_memory_usage","args":{"memory_threshold_mb":1024}}',
        'Final Answer: 已完成'])
    agent.run("模拟问题")
    assert calls == [{"memory_threshold_mb": 1024}]
    assert model.chat.call_count == 3 and not observed["errors"]
    assert any("INVALID_ARGS" in entry[2] for entry in observed["observations"])


def test_agent_denied_tool_never_executes_or_continues(monkeypatch):
    agent, model, calls, observed = make_agent(monkeypatch, [
        'Action: {"tool":"run_program","args":{"command":"anything"}}'])
    agent.run("模拟问题")
    assert model.chat.call_count == 1 and not calls
    assert observed["errors"] and not observed["finals"]
    assert observed["traces"][-1]["tool_result"]["code"] == "PERMISSION_DENIED"


def test_agent_stops_before_execution_when_cancelled_after_model_reply(monkeypatch):
    agent, model, calls, observed = make_agent(monkeypatch, [
        'Action: {"tool":"get_current_directory","args":{}}'])
    agent.stop_flag = lambda: model.chat.call_count > 0
    agent.run("模拟问题")
    assert not calls and not observed["finals"]


def test_agent_keeps_global_iteration_limit(monkeypatch):
    from sys_agent.react_agent import MAX_ITERATIONS
    agent, model, calls, observed = make_agent(monkeypatch, [
        'Action: {"tool":"get_current_directory","args":{}}'] * MAX_ITERATIONS)
    agent.run("模拟问题")
    assert model.chat.call_count == MAX_ITERATIONS and len(calls) == MAX_ITERATIONS
    assert observed["errors"] and not observed["finals"]
