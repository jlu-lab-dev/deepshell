# message_helpers.py
# 统一 JSON 消息格式的构造与解析辅助函数

import json
from typing import Optional


def is_json_message(content: str) -> bool:
    """判断 content 是否为 JSON 格式消息。"""
    return isinstance(content, str) and content.startswith("{")


def parse_message_content(content: str) -> dict:
    """解析消息 content JSON → dict。非 JSON 时返回原始字符串包装。"""
    if is_json_message(content):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
    return {"type": "text", "content": content}


def get_text_content(content: str) -> str:
    """
    从消息 content 中提取用于 LLM 上下文重建的文本。
    - text 类型：用 build_llm_context 从 user_input / attachment_content / relevant_docs 重建完整上下文
    - agent_memory：返回 final_answer
    - agent_workflow：返回 final_result
    """
    data = parse_message_content(content)
    msg_type = data.get("type", "text")
    if msg_type == "text":
        # 有结构化字段时，用 build_llm_context 重建完整 LLM 上下文
        if "user_input" in data:
            return build_llm_context(
                user_input=data["user_input"],
                attachment_content=data.get("attachment_content"),
                relevant_docs=data.get("relevant_docs"),
            )
        return data.get("content", content)
    elif msg_type == "agent_memory":
        return data.get("final_answer", content)
    elif msg_type == "agent_workflow":
        return data.get("final_result", content)
    elif msg_type == "summary":
        return f"[历史对话摘要]\n{data.get('summary', '')}"
    return content


def make_text_message(role: str, *,
                     user_input: str = "",
                     attachment_content: list = None,
                     relevant_docs: list = None) -> str:
    """
    构造 type=text JSON 消息字符串。
    content 字段由 build_llm_context 自动生成，不需要手动传入。
    """
    obj = {
        "role": role,
        "type": "text",
        "user_input": user_input,
    }
    if attachment_content is not None:
        obj["attachment_content"] = attachment_content
    if relevant_docs is not None:
        obj["relevant_docs"] = relevant_docs
    # content 由结构化字段自动生成
    obj["content"] = build_llm_context(user_input, attachment_content, relevant_docs)
    return json.dumps(obj, ensure_ascii=False)


def get_message_parts(content: str) -> dict:
    """
    从消息 content 中提取各部分，用于 UI 渲染。
    返回 {"user_input", "attachment_content", "relevant_docs", "content"}
    """
    data = parse_message_content(content)
    return {
        "user_input": data.get("user_input", ""),
        "attachment_content": data.get("attachment_content", []),
        "relevant_docs": data.get("relevant_docs", []),
        "content": data.get("content", ""),
    }


def build_llm_context(user_input: str, attachment_content: list = None,
                      relevant_docs: list = None) -> str:
    """
    根据各部分组装发给 LLM 的完整字符串。
    用于从结构化字段重建上下文，或在 make_text_message 中自动生成 content。
    """
    parts = [user_input]

    if attachment_content:
        for i, att in enumerate(attachment_content):
            name = att.get("name", f"附件{i+1}")
            text = att.get("content", "")
            parts.append(f"用户上传附件内容 {i+1}：{name}\n{text}")

    if relevant_docs:
        doc_parts = []
        for doc in relevant_docs:
            source = doc.get("source", "未知来源")
            text = doc.get("content", "")
            doc_parts.append(f"[Document] (Source: {source})\n{text}")
        if doc_parts:
            parts.append("参考以下信息回答用户问题：\n" + "\n\n".join(doc_parts))

    return "\n\n".join(parts)


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


# ── Summary (memory compression) ──────────────────────────────────────

def make_summary_message(summary_text: str) -> str:
    """构造 type=summary JSON 消息字符串（role=system）。"""
    return json.dumps({
        "role": "system",
        "type": "summary",
        "summary": summary_text,
    }, ensure_ascii=False)


def get_summary_text(content: str) -> str:
    """从 summary 消息中提取摘要文本。非 summary 类型返回空字符串。"""
    data = parse_message_content(content)
    if data.get("type") == "summary":
        return data.get("summary", "")
    return ""


def make_compressed_marker(content_json: str) -> str:
    """
    将原始消息 JSON 标记为已压缩：在原始 JSON 中追加 "compressed": true。
    已压缩的消息：UI 可渲染，但 LLM 上下文 / Agent 历史加载时跳过。
    """
    try:
        data = json.loads(content_json) if is_json_message(content_json) else {"type": "text", "content": content_json}
    except json.JSONDecodeError:
        data = {"type": "text", "content": content_json}
    data["compressed"] = True
    return json.dumps(data, ensure_ascii=False)


def is_compressed(content: str) -> bool:
    """判断消息是否已被标记为压缩。"""
    if not is_json_message(content):
        return False
    try:
        return json.loads(content).get("compressed", False) is True
    except json.JSONDecodeError:
        return False
