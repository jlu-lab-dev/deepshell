"""DeepShell Agent 工具参数与返回值模型。

所属模块：sys_agent。
主要职责：把现有 toolkits/*.json 中的简单 JSON Schema 转成严格的 Pydantic 校验器，
并统一执行结果；本模块不执行任何系统命令，也不访问用户文件。
支持现有工具使用的字符串、整数、布尔、数值、数组和 JSON 对象。
"""

from __future__ import annotations

import re
from typing import Any, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, create_model, model_validator


class StrictToolArgs(BaseModel):
    """禁止意外参数和隐式类型转换：例如不把字符串 '1024' 当成整数。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    @model_validator(mode="after")
    def require_json_arguments(self):
        import json
        try:
            json.dumps(self.model_dump(exclude_unset=True), allow_nan=False)
        except (ValueError, TypeError) as exc:
            raise ValueError("参数必须是有限、可序列化的 JSON 值") from exc
        return self


class ToolResult(BaseModel):
    """工具执行的统一结果，供 ReAct Observation、GUI 和测试使用。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    tool: str
    success: bool
    code: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    retryable: bool = False
    elapsed_ms: float = 0.0


def build_args_model(tool_name: str, parameter_schema: dict[str, Any]) -> type[StrictToolArgs]:
    """依据现有工具 JSON 定义创建严格的参数校验模型。

    不支持的 JSON Schema 必须显式拒绝，不能悄悄放宽校验。
    全部已注册工具都通过此校验器，工作区文本工具另有更严格的专用模型。
    """
    if not isinstance(parameter_schema, dict) or parameter_schema.get("type") != "object":
        raise ValueError(f"{tool_name}: 工具参数必须是 object Schema")

    properties = parameter_schema.get("properties", {})
    required = parameter_schema.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list):
        raise ValueError(f"{tool_name}: properties / required 格式错误")
    if any(name not in properties for name in required):
        raise ValueError(f"{tool_name}: required 中存在未声明字段")

    def value_type(spec, param):
        kind = spec.get("type")
        if kind == "string":
            minimum = 0 if param in {"content", "body"} else 1
            return Annotated[str, Field(min_length=spec.get("minLength", minimum),
                                        max_length=spec.get("maxLength", 131072))]
        if kind == "integer":
            bounds = {}
            if param == "memory_threshold_mb":
                bounds = dict(ge=1, le=1_000_000)
            elif param == "pid":
                bounds = dict(ge=1)
            elif param == "search_depth":
                bounds = dict(ge=0, le=100)
            return Annotated[int, Field(**bounds)]
        if kind == "number":
            return Annotated[float, Field(allow_inf_nan=False)]
        if kind == "boolean":
            return bool
        if kind == "array":
            item = value_type(spec["items"], param) if spec.get("items") else JsonValue
            return Annotated[list[item], Field(max_length=10000)]
        if kind == "object":
            return dict[str, JsonValue]
        raise ValueError(f"{tool_name}.{param}: 不支持的参数类型 {kind}")

    fields: dict[str, tuple[type, Any]] = {}
    for param, spec in properties.items():
        if not isinstance(spec, dict):
            raise ValueError(f"{tool_name}.{param}: 暂不支持的参数类型")
        annotation = value_type(spec, param)
        if spec.get("enum"):
            annotation = Literal[tuple(spec["enum"])]
        default = ... if param in required else None
        fields[param] = (annotation, Field(default=default))

    safe_class_name = "Args_" + re.sub(r"\W", "_", tool_name)
    return create_model(safe_class_name, __base__=StrictToolArgs, **fields)
