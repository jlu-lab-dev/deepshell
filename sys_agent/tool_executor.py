"""DeepShell Agent 安全工具执行入口。

所属模块：sys_agent。
主要职责：按固定白名单选择工具、严格参数校验、统一执行结果和失败分类。
GUI 全工具配置提供全部原有工具；只读查询直接执行，其余逐次审批。
历史评测继续使用四工具配置，独立的 create_text_file 仍保留工作区限制。
注意：同步 Python 函数调用没有可强制终止的超时；超时与取消需要后续隔离执行设计。
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from sys_agent.tool_registry import SAFE_TOOL_NAMES, ToolRegistry
from sys_agent.tool_schema import ToolResult
from sys_agent.tool_approval import ApprovalStore, OperationApprovalStore
from sys_agent.tool_policy import ALL_TOOL_NAMES, APPROVAL_EFFECTS, freeze_paths


class ToolExecutor:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        workspace = os.environ.get("DEEPSHELL_AGENT_WORKSPACE") or str(Path.cwd() / "agent_workspace")
        self.approvals = ApprovalStore(workspace)
        self.operation_approvals = OperationApprovalStore()

    def get_pending_approval(self, request_id: str) -> dict | None:
        """仅供本地审批界面读取，不向模型返回正文。"""
        return self.operation_approvals.get_for_review(request_id) or self.approvals.get_for_review(request_id)

    def resolve_pending_approval(self, request_id: str, approved: bool) -> ToolResult:
        started = time.perf_counter()
        if self.operation_approvals.get_for_review(request_id) is not None:
            permitted = (self.registry.full_tools and os.environ.get('DEEPSHELL_ENABLE_ALL_TOOLS') == '1')
            outcome = self.operation_approvals.resolve(request_id, approved is True and permitted)
            return ToolResult(**outcome)
        approved = approved is True and os.environ.get("DEEPSHELL_ENABLE_APPROVED_WRITE") == "1"
        outcome = self.approvals.resolve(request_id, approved)
        return ToolResult(
            tool="create_text_file", success=outcome["success"],
            code=outcome["code"], message=outcome["message"],
            data=outcome.get("data", {}), retryable=False,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 3))

    def execute(self, tool_name: str, arguments: Any) -> ToolResult:
        """未知/未授权/参数非法的工具不执行；成功则归一化原有 atomic_result 字典。"""
        started = time.perf_counter()

        def fail(code: str, message: str, retryable: bool = False) -> ToolResult:
            return ToolResult(
                tool=str(tool_name), success=False, code=code, message=message,
                retryable=retryable, elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
            )

        if not isinstance(tool_name, str) or not tool_name:
            return fail("INVALID_ARGS", "工具名称必须是非空字符串", retryable=True)

        registered = self.registry.get(tool_name)
        approved_write = tool_name == "create_text_file" and os.environ.get("DEEPSHELL_ENABLE_APPROVED_WRITE") == "1"
        permitted_full = self.registry.full_tools and tool_name in ALL_TOOL_NAMES and os.environ.get('DEEPSHELL_ENABLE_ALL_TOOLS') == '1'
        if tool_name not in SAFE_TOOL_NAMES and not approved_write and not permitted_full and (registered is not None or tool_name in self.registry.known_names):
            return fail("PERMISSION_DENIED", "此工具暂未授权给 Agent")
        if registered is None:
            if tool_name in self.registry.known_names:
                return fail("PERMISSION_DENIED", "此工具暂未授权给 Agent")
            return fail("UNKNOWN_TOOL", "不存在指定工具", retryable=True)
        if registered.name != tool_name:
            return fail("TOOL_ERROR", "工具注册名称不一致")

        if not isinstance(arguments, dict):
            return fail("INVALID_ARGS", "工具参数 args 必须是 JSON 对象", retryable=True)

        try:
            # strict + extra=forbid：拒绝误类型、未声明字段、必填字段缺失。
            validated = registered.args_model.model_validate(arguments)
        except ValidationError as exc:
            first = exc.errors()[0]
            return fail("INVALID_ARGS", f"参数校验失败：{first['loc']} - {first['msg']}", retryable=True)

        if tool_name == "create_text_file":
            ticket = self.approvals.prepare(**validated.model_dump())
            return ToolResult(
                tool=tool_name, success=False, code="PENDING_APPROVAL",
                message="等待用户确认创建文件", data={"request_id": ticket["request_id"]},
                retryable=False, elapsed_ms=round((time.perf_counter() - started) * 1000, 3))

        arguments = validated.model_dump(exclude_unset=True)
        if permitted_full and tool_name in APPROVAL_EFFECTS:
            try:
                arguments = freeze_paths(tool_name, arguments)
                handler, extra_preview = registered.handler, None
                planner = getattr(handler, 'approval_plan_factory', None)
                if planner is not None:
                    handler, extra_preview = planner(**arguments)
                request_id = self.operation_approvals.prepare(
                    tool_name, arguments,
                    lambda frozen, handler=handler: self._invoke(tool_name, handler, frozen),
                    APPROVAL_EFFECTS[tool_name], extra_preview)
            except Exception as exc:
                return fail('TOOL_ERROR', f'准备审批失败：{type(exc).__name__}')
            return ToolResult(tool=tool_name, success=False, code='PENDING_APPROVAL',
                              message='等待用户批准工具操作', data={'request_id': request_id})
        return self._invoke(tool_name, registered.handler, arguments)

    @staticmethod
    def _invoke(tool_name, handler, arguments):
        started = time.perf_counter()

        def fail(code, message):
            return ToolResult(tool=tool_name, success=False, code=code, message=message,
                              elapsed_ms=round((time.perf_counter() - started) * 1000, 3))

        try:
            raw = handler(**arguments)
        except Exception as exc:
            return fail("TOOL_ERROR", f"工具执行异常：{type(exc).__name__}")

        if not isinstance(raw, dict) or not isinstance(raw.get("success"), bool):
            return fail("TOOL_ERROR", "工具没有返回符合 atomic_result 约定的结果")

        try:
            success = raw["success"]
            result = ToolResult(
                tool=tool_name, success=success,
                code="SUCCESS" if success else "TOOL_FAILED",
                message=str(raw.get("message", ""))[:2000],
                data={k: v for k, v in raw.items() if k not in ("success", "message")},
                retryable=False,
                elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
            )
            # Observation 必须能写成合法 JSON，坏返回值不得让 Agent 在序列化时崩溃。
            # 先检查 Python 原值，避免 JSON 模式将 NaN/Infinity 转为 null 后漏检。
            json.dumps(result.model_dump(mode="python"), ensure_ascii=False, allow_nan=False)
            return result
        except Exception as exc:
            return fail("TOOL_ERROR", f"工具返回值无法序列化：{type(exc).__name__}")
