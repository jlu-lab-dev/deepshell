"""DeepShell Agent 统一工具注册中心。

所属模块：sys_agent。
复用现有 experts.json + FUNCTION_MAP；GUI 全工具配置使用显式策略，区分只读与逐次审批。
SAFE_TOOL_NAMES 保留历史四工具评测配置；模型不能修改权限或批准操作。
"""

from __future__ import annotations

from copy import deepcopy
import os
from dataclasses import dataclass
from typing import Any, Callable

from sys_agent.tool_schema import StrictToolArgs, build_args_model
from sys_agent.tool_approval import CREATE_TEXT_FILE_SCHEMA, CreateTextFileArgs, blocked_direct_handler
from sys_agent.tool_policy import ALL_TOOL_NAMES, APPROVAL_EFFECTS


# 历史四工具配置继续用于原来的固定评测；GUI 配置使用 ALL_TOOL_NAMES。
SAFE_TOOL_NAMES = frozenset({
    "get_current_directory",
    "get_user_folder_path",
    "list_running_applications",
    "list_applications_by_memory_usage",
})


@dataclass(frozen=True)
class RegisteredTool:
    name: str
    schema: dict[str, Any]
    handler: Callable[..., Any]
    args_model: type[StrictToolArgs]


class ToolRegistry:
    """从已有工具数据创建安全工具视图，不重复发明工具定义。"""

    def __init__(self, tools: dict[str, RegisteredTool], known_names: frozenset[str], *, full_tools=False):
        self._tools = tools
        self.known_names = known_names
        self.full_tools = full_tools

    @classmethod
    def from_existing(cls, schemas: list[dict], function_map: dict[str, Callable], *, allow_approved_write: bool = True):
        """默认拒绝：只有同时在 Schema、实现映射、固定 allowlist 的工具才可执行。"""
        full_tools = allow_approved_write and os.environ.get("DEEPSHELL_ENABLE_ALL_TOOLS") == "1"
        allowed_names = ALL_TOOL_NAMES if full_tools else SAFE_TOOL_NAMES
        tools: dict[str, RegisteredTool] = {}
        known_names = frozenset(
            [x["name"] for x in schemas if isinstance(x, dict) and isinstance(x.get("name"), str)]
            + [name for name in function_map if isinstance(name, str)]
        )
        for schema in schemas:
            name = schema.get("name") if isinstance(schema, dict) else None
            if name not in allowed_names:
                continue
            if name not in function_map:
                raise ValueError(f"安全工具 {name} 缺少 FUNCTION_MAP 处理函数")
            if not callable(function_map[name]):
                raise ValueError(f"安全工具 {name} 的处理函数不可调用")
            if name in tools:
                raise ValueError(f"发现重复工具名称：{name}")
            visible_schema = deepcopy(schema)
            if name in APPROVAL_EFFECTS:
                visible_schema['description'] = str(schema.get('description', '')) + '【需用户逐次批准】' + APPROVAL_EFFECTS[name]
            if name == 'get_contact_email':
                visible_schema['description'] = '查询项目当前内置的示例联系人表，不读取系统通讯录；未配置的姓名会查找失败。'
            visible_schema.setdefault('parameters', {})['additionalProperties'] = False
            tools[name] = RegisteredTool(
                name=name,
                schema=visible_schema,
                handler=function_map[name],
                args_model=build_args_model(name, schema.get("parameters", {})),
            )
        if allow_approved_write and os.environ.get("DEEPSHELL_ENABLE_APPROVED_WRITE") == "1":
            if "create_text_file" in known_names:
                raise ValueError("create_text_file 与已有工具名冲突")
            tools["create_text_file"] = RegisteredTool(
                name="create_text_file", schema=deepcopy(CREATE_TEXT_FILE_SCHEMA),
                handler=blocked_direct_handler, args_model=CreateTextFileArgs)
            known_names = known_names | frozenset({"create_text_file"})
        return cls(tools=tools, known_names=known_names, full_tools=full_tools)

    def get(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def get_tool_schemas(self) -> list[dict]:
        """返回当前配置允许的工具 Schema，并保留审批说明。"""
        return [deepcopy(t.schema) for t in self._tools.values()]

    def get_function_map(self) -> dict[str, Callable]:
        """供当前 Controller 兼容使用；安全执行仍必须经过 ToolExecutor。"""
        return {name: (blocked_direct_handler if name in APPROVAL_EFFECTS or name == 'create_text_file'
                       else tool.handler) for name, tool in self._tools.items()}
