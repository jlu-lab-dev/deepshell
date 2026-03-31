# sys_agent/toolkits/_base.py
# 共享工具基础设施：统一返回类型、路径处理、输入校验。
# 所有 toolkits 模块统一引用此文件，消除 atomic_result 的重复定义。

from __future__ import annotations

import os
import platform
from dataclasses import dataclass, field
from typing import Any


# ──────────────────────────────────────────────────────────────
# 统一返回类型
# ──────────────────────────────────────────────────────────────

@dataclass
class ToolResult:
    """
    所有工具函数的标准返回类型。

    Attributes:
        success: 操作是否成功。
        message: 面向用户的结果描述（自然语言，LLM 可直接引用）。
        data:   结构化数据载荷（可选），如文件路径列表、表格 JSON 等。
    """

    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict，供 ReAct Agent 消费。"""
        result: dict[str, Any] = {
            "success": self.success,
            "message": self.message,
        }
        result.update(self.data)
        return result


def ok(message: str, **data: Any) -> dict[str, Any]:
    """快捷构造成功结果。"""
    return ToolResult(success=True, message=message, data=data).to_dict()


def fail(message: str, **data: Any) -> dict[str, Any]:
    """快捷构造失败结果。"""
    return ToolResult(success=False, message=message, data=data).to_dict()


# ──────────────────────────────────────────────────────────────
# 路径处理
# ──────────────────────────────────────────────────────────────

def expanduser(path: str) -> str:
    """
    兼容 Windows 的 os.path.expanduser。
    处理 ~ 开头的路径，使其在所有平台上正确展开。
    """
    if "~" not in path:
        return path
    if platform.system() == "Windows":
        import getpass
        home = os.path.join("C:\\Users", getpass.getuser())
        return path.replace("~", home)
    return os.path.expanduser(path)


def resolve_path(path: str) -> str:
    """展开 ~ 并规范化路径分隔符。"""
    return os.path.normpath(expanduser(path))


def require_non_empty(value: Any, field_name: str) -> None:
    """简单校验：值非空字符串 / 非空列表。"""
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError(f"参数 '{field_name}' 不能为空")


def require_positive_int(value: Any, field_name: str) -> None:
    """简单校验：正整数。"""
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"参数 '{field_name}' 必须是正整数，当前值: {value}")
