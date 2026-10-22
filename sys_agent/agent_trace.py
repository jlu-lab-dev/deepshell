"""DeepShell Agent Trace：记录脱敏的结构化执行轨迹。

所属模块：sys_agent（Agent 可观测性）。
主要职责：为每次 ReAct 任务生成 trace_id，保存步骤、工具状态、耗时和停止原因。
安全约束：不会存储用户原文、模型 Thought、工具参数值、Observation 原文或工具数据。
默认不由该模块自动启用；调用方按需传入 TraceRecorder 或通过配置显式启用。
"""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_WRITE_LOCK = threading.Lock()
_ALLOWED_EVENTS = frozenset({
    "task_started", "model_result", "tool_result", "task_finished"
})
_ALLOWED_END_REASONS = frozenset({
    "completed", "plain_answer", "model_error", "parse_error",
    "tool_error", "permission_denied", "cancelled", "max_iterations"
})


class TraceRecorder:
    """每个任务独立 JSONL 文件；只接受明确允许的字段，默认拒绝敏感文本。"""

    def __init__(self, output_dir: str | Path, task_id: str = ""):
        self.trace_id = uuid.uuid4().hex
        self.task_id = task_id[:64]  # 评测任务 ID，不应传入用户文本
        self.output_dir = Path(output_dir)
        self.path = self.output_dir / f"{self.trace_id}.jsonl"
        self._started = time.perf_counter()
        self.events: list[dict[str, Any]] = []

    def record(self, kind: str, *, iteration: int | None = None,
               tool: str = "", code: str = "", success: bool | None = None,
               elapsed_ms: float | None = None, reason: str = "",
               argument_keys: list[str] | None = None,
               model_name: str = "") -> None:
        """白名单字段写入；不提供任意 payload 参数，防止误将隐私落盘。"""
        if kind not in _ALLOWED_EVENTS:
            raise ValueError(f"不支持的 Trace 事件：{kind}")
        if kind == "task_finished" and reason not in _ALLOWED_END_REASONS:
            raise ValueError(f"不支持的任务结束原因：{reason}")
        event = {
            "trace_id": self.trace_id,
            "task_id": self.task_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": kind,
        }
        if iteration is not None:
            event["iteration"] = int(iteration)
        if tool:
            # 模型可能伪造包含用户文本的“工具名”，只允许标准标识符落盘。
            event["tool"] = tool if isinstance(tool, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", tool) else "INVALID_TOOL_NAME"
        if code:
            event["code"] = str(code)[:50]
        if success is not None:
            event["success"] = bool(success)
        if elapsed_ms is not None:
            event["elapsed_ms"] = round(max(0.0, float(elapsed_ms)), 3)
        if reason:
            event["reason"] = reason
        if argument_keys is not None:
            # 只记字段名，不记路径、命令、文件名或其它参数值。
            event["argument_keys"] = sorted(
                k if isinstance(k, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", k)
                else "INVALID_ARGUMENT_KEY" for k in argument_keys
            )[:30]
        if model_name:
            event["model_name"] = model_name[:80]
        self.events.append(event)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with _WRITE_LOCK:
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")

    def finish(self, reason: str, *, iteration: int | None = None) -> None:
        if self.events and self.events[-1]["event"] == "task_finished":
            return
        self.record("task_finished", reason=reason, iteration=iteration,
                    elapsed_ms=(time.perf_counter() - self._started) * 1000)
