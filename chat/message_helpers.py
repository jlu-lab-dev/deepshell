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
    msg_type = data.get("type", "text")
    if msg_type == "text":
        return data.get("content", content)
    elif msg_type == "agent_memory":
        return data.get("final_answer", content)
    elif msg_type == "agent_workflow":
        return data.get("final_result", content)
    return content


def make_text_message(role: str, text: str) -> str:
    """构造 type=text JSON 消息字符串。"""
    obj = {"role": role, "type": "text", "content": text}
    return json.dumps(obj, ensure_ascii=False)


def make_agent_workflow_message(
    role: str,
    mode: str,
    final_result: str,
    thought_chain: Optional[list] = None,
) -> str:
    """构造 type=agent_workflow JSON 消息字符串。"""
    obj = {
        "role": role,
        "type": "agent_workflow",
        "mode": mode,
        "final_result": final_result,
    }
    if thought_chain:
        obj["thought_chain"] = thought_chain
    return json.dumps(obj, ensure_ascii=False)


def make_agent_memory_message(tool_results: list, final_answer: str) -> str:
    """
    构建 type=agent_memory 的紧凑记忆消息。
    供 load_history 快速重建上下文，不包含完整推理过程。
    """
    obj = {
        "role": "assistant",
        "type": "agent_memory",
        "tool_results": tool_results,    # [{"tool": ..., "result_summary": ...}]
        "final_answer": final_answer,
    }
    return json.dumps(obj, ensure_ascii=False)


def get_agent_memory_content(content: str) -> list:
    """
    从 agent_memory 消息中提取紧凑历史字符串列表。
    返回格式如 ["Observation (tool=xxx): ...", "助手回答：..."]
    """
    data = parse_message_content(content)
    if data.get("type") != "agent_memory":
        return []
    result = []
    for tr in data.get("tool_results", []):
        result.append(f"Observation (tool={tr['tool']}): {tr['result_summary']}")
    final = data.get("final_answer", "")
    if final:
        result.append(f"助手回答：{final}")
    return result
