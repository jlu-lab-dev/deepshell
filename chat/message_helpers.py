# message_helpers.py
# 统一 JSON 消息格式的构造与解析辅助函数

import json
from typing import Optional


def is_json_message(content: str) -> bool:
    """判断 content 是否为 JSON 格式消息。"""
    return isinstance(content, str) and content.startswith("{")


def parse_message_content(content: str) -> dict:
    """
    解析消息 content，统一入口：
    - JSON 格式 → 返回 dict
    - 纯文本（旧格式兼容）→ 返回 {"type": "text", "content": 原文}
    """
    if is_json_message(content):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
    return {"type": "text", "content": content}


def get_text_content(content: str) -> str:
    """从任意格式 content 中提取纯文本（用于 LLM 上下文重建）。"""
    data = parse_message_content(content)
    if data.get("type") == "text":
        return data.get("content", content)
    return data.get("final_result", content)


def make_text_message(role: str, text: str) -> str:
    """构造 type=text JSON 消息字符串。"""
    obj = {"role": role, "type": "text", "content": text}
    return json.dumps(obj, ensure_ascii=False)


def make_agent_workflow_message(
    role: str,
    mode: str,
    final_result: str,
    steps: list,
    thought_chain: Optional[list] = None,
) -> str:
    """构造 type=agent_workflow JSON 消息字符串。"""
    obj = {
        "role": role,
        "type": "agent_workflow",
        "mode": mode,
        "final_result": final_result,
        "steps": steps,
    }
    if thought_chain:
        obj["thought_chain"] = thought_chain
    return json.dumps(obj, ensure_ascii=False)
