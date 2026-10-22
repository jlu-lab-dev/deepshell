"""Agent Trace 的独立离线测试，不调用 Qt/Qwen/真实系统工具。"""
import json
import pytest
from sys_agent.agent_trace import TraceRecorder


def test_trace_contains_no_private_text(tmp_path):
    t = TraceRecorder(tmp_path, task_id="AGENT-001")
    t.record("task_started", model_name="fake")
    t.record("tool_result", iteration=1, tool="get_user_folder_path", code="SUCCESS",
             success=True, argument_keys=["folder_name"], elapsed_ms=2)
    t.finish("completed", iteration=2)
    events = [json.loads(x) for x in t.path.read_text(encoding="utf8").splitlines()]
    assert len(events) == 3
    assert all(e["trace_id"] == t.trace_id for e in events)
    assert events[-1]["reason"] == "completed"
    raw = t.path.read_text(encoding="utf8")
    assert "Downloads" not in raw
    assert "用户" not in raw
    assert "folder_name" in raw


def test_finish_idempotent(tmp_path):
    t = TraceRecorder(tmp_path)
    t.finish("plain_answer")
    t.finish("plain_answer")
    assert len(t.events) == 1


def test_reject_unknown_events_and_reasons(tmp_path):
    t = TraceRecorder(tmp_path)
    with pytest.raises(ValueError):
        t.record("dump_model_thought")
    with pytest.raises(ValueError):
        t.finish("unknown")


def test_trace_sanitizes_untrusted_tool_and_argument_names(tmp_path):
    trace = TraceRecorder(tmp_path)
    trace.record("tool_result", tool=r"C:\private\secret.txt",
                 code="INVALID_ARGS", argument_keys=[r"C:\private\secret.txt", "folder_name", 123])
    raw = trace.path.read_text(encoding="utf-8")
    assert "private" not in raw and "secret.txt" not in raw
    assert trace.events[0]["tool"] == "INVALID_TOOL_NAME"
    assert trace.events[0]["argument_keys"] == ["INVALID_ARGUMENT_KEY", "INVALID_ARGUMENT_KEY", "folder_name"]
    with pytest.raises(TypeError):
        trace.record("model_result", payload="private response")


def make_traced_agent(monkeypatch, trace, responses):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from evals.agent_eval import fake_handlers, load_existing_tool_schemas
    from sys_agent import react_agent

    # 即使本机没有 API 配置，注入模型后也不能初始化真实模型客户端。
    def forbidden_initialization():
        raise AssertionError("must use injected model")
    monkeypatch.setattr(react_agent, "ModelManager", forbidden_initialization)
    handlers, calls = fake_handlers()
    final, errors = [], []
    model = SimpleNamespace(chat=Mock(side_effect=responses))
    agent = react_agent.ReActAgent(
        "fake", load_existing_tool_schemas(), handlers,
        lambda *_: None, lambda *_: None, final.append, errors.append, lambda: False,
        trace_recorder=trace, model_manager=model)
    return agent, model, calls, final, errors


@pytest.mark.parametrize("responses,reason", [
    (["Final Answer: private final answer"], "completed"),
    (["private plain answer"], "plain_answer"),
    ([RuntimeError("private API error")], "model_error"),
    (["Action: {", "Action: {"], "parse_error"),
    (['Action: {"tool":"delete_file","args":{"path":"private.txt"}}'], "permission_denied"),
    (['Action: {"tool":"missing","args":{}}'] * 2, "tool_error"),
    (['Action: {"tool":"get_current_directory","args":{}}'] * 8, "max_iterations"),
])
def test_agent_records_each_stop_reason(monkeypatch, tmp_path, responses, reason):
    trace = TraceRecorder(tmp_path)
    agent, _, calls, _, _ = make_traced_agent(monkeypatch, trace, responses)
    agent.run("private user input")
    events = [json.loads(line) for line in trace.path.read_text(encoding="utf-8").splitlines()]
    assert events[0]["event"] == "task_started"
    assert sum(event["event"] == "task_finished" for event in events) == 1
    assert events[-1]["reason"] == reason
    assert "private" not in trace.path.read_text(encoding="utf-8")
    if reason == "permission_denied":
        assert not calls


@pytest.mark.parametrize("after_reply", [False, True])
def test_cancellation_trace_does_not_execute_tools(monkeypatch, tmp_path, after_reply):
    trace = TraceRecorder(tmp_path)
    agent, model, calls, _, _ = make_traced_agent(monkeypatch, trace, [
        'Action: {"tool":"get_current_directory","args":{}}'])
    agent.stop_flag = lambda: bool(model.chat.call_count) if after_reply else True
    agent.run("private user input")
    assert trace.events[-1]["reason"] == "cancelled"
    assert not calls


def test_nonretryable_tool_error_finishes_trace_immediately(monkeypatch, tmp_path):
    from sys_agent.tool_registry import RegisteredTool
    trace = TraceRecorder(tmp_path)
    agent, model, _, _, errors = make_traced_agent(monkeypatch, trace, [
        'Action: {"tool":"get_current_directory","args":{}}'])
    tool = agent.tool_registry.get("get_current_directory")
    agent.tool_registry._tools[tool.name] = RegisteredTool(
        tool.name, tool.schema, lambda: {"success": False, "message": "private failure"}, tool.args_model)
    agent.run("private user input")
    assert errors and model.chat.call_count == 1
    assert trace.events[-1]["reason"] == "tool_error"


def test_trace_io_failure_does_not_break_agent(monkeypatch, tmp_path):
    from unittest.mock import Mock
    trace = TraceRecorder(tmp_path)
    trace.record = Mock(side_effect=OSError("private path"))
    trace.finish = Mock(side_effect=OSError("private path"))
    agent, _, _, final, errors = make_traced_agent(monkeypatch, trace, ["Final Answer: done"])
    agent.run("private user input")
    assert final == ["done"] and not errors
