"""
memory_compressor.py
滑动窗口 + LLM 摘要压缩，用于普通对话和 Agent 历史的内存管理。

设计原则：
- 不删除 DB 中的原始消息，只在消息 JSON 中追加 "compressed": true 标记
- 摘要以 role=system/type=summary 存入 DB（不参与 LLM 上下文，由内存注入）
- 重建内存时：摘要拼接到第一条 HumanMessage 前面，不碰 SystemMessage
- 异步压缩时持锁重建，防止压缩期间的新消息被吞掉
"""

import logging
from typing import List, Optional

from utils.decorators import singleton
from config.config_manager import ConfigManager
from chat.message_helpers import (
    parse_message_content,
    make_summary_message,
    get_summary_text,
    get_text_content,
    get_agent_memory_content,
    make_compressed_marker,
    is_compressed,
)

COMPRESS_PROMPT = """请将以下历史对话内容压缩为一段简洁的摘要，保留所有关键信息\
（用户意图、重要结论、达成的共识、涉及的工具调用等）。\
摘要将作为后续对话的上下文补充，字数控制在{max_tokens}字以内。

历史对话内容：
{conversation}

请直接输出摘要，不要包含任何前言或解释性文字。"""


@singleton
class MemoryCompressor:
    def __init__(self):
        config_manager = ConfigManager()
        rag_cfg = config_manager.get_rag_config()
        mem_cfg = rag_cfg.get("memory", {})

        self.enabled: bool = mem_cfg.get("compress_enabled", True)
        self.threshold_rounds: int = mem_cfg.get("compress_threshold_rounds", 10)
        self.keep_recent_rounds: int = mem_cfg.get("keep_recent_rounds", 4)
        self.compress_model: str = mem_cfg.get("compress_model", "DeepSeek-V3")
        self.max_summary_tokens: int = mem_cfg.get("max_summary_tokens", 500)
        self.agent_max_history_chars: int = mem_cfg.get("agent_max_history_chars", 4000)

    # ── Public API ────────────────────────────────────────────────────────────

    def maybe_compress(self, conversation_id: str, conversation_repo) -> bool:
        """
        检查是否需要压缩。超过阈值时触发压缩，否则直接返回 False。
        调用方须已持有 session 对应的压缩锁。
        """
        if not self.enabled:
            return False
        try:
            db_messages = conversation_repo.get_messages(conversation_id)
            rounds = self._count_rounds(db_messages)
            logging.info(
                f"[MemoryCompressor] conversation={conversation_id[:8]}.. "
                f"rounds={rounds} threshold={self.threshold_rounds}"
            )
            if rounds < self.threshold_rounds:
                return False
            return self._compress(conversation_id, conversation_repo, db_messages)
        except Exception as e:
            logging.error(f"[MemoryCompressor] maybe_compress failed: {e}")
            return False

    def compress_agent_history(self, history_entries: List[str]) -> List[str]:
        """
        对 Agent 历史字符串列表进行字符数截断（从头部丢弃）。
        上限由 agent_max_history_chars 配置。
        """
        total = sum(len(s) for s in history_entries)
        if total <= self.agent_max_history_chars:
            return history_entries

        result = []
        running = 0
        for entry in reversed(history_entries):
            if running + len(entry) > self.agent_max_history_chars:
                break
            result.insert(0, entry)
            running += len(entry)

        logging.warning(
            f"[MemoryCompressor] Agent history truncated: {total} → {running} chars "
            f"({len(result)}/{len(history_entries)} entries kept)"
        )
        return result

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _count_rounds(self, db_messages) -> int:
        """统计 user 轮次（排除 summary/compressed 消息）。"""
        count = 0
        for msg in db_messages:
            if msg.role == "user":
                data = parse_message_content(msg.content)
                msg_type = data.get("type", "text")
                if msg_type in ("summary", "compressed"):
                    continue
                count += 1
        return count

    def _compress(self, conversation_id: str, conversation_repo, db_messages) -> bool:
        """
        执行压缩（调用方已持有锁）：
        生成摘要 → 标记旧消息为 compressed → 写入 summary → 重建内存。
        """
        # 过滤掉已压缩的消息和 summary，只处理原始对话
        active_msgs = [
            m for m in db_messages
            if not (
                (m.role == "system" and parse_message_content(m.content).get("type") == "summary")
                or is_compressed(m.content)
            )
        ]

        rounds_to_compress = self._count_rounds(active_msgs) - self.keep_recent_rounds
        if rounds_to_compress <= 0:
            return False

        old_msgs, recent_msgs = self._split_messages(active_msgs, rounds_to_compress)
        if not old_msgs:
            return False

        # 生成摘要
        old_text = self._build_old_text(old_msgs)
        summary = self._generate_summary(old_text)
        if not summary:
            logging.warning("[MemoryCompressor] LLM returned empty summary; skipping compression")
            return False

        # 标记旧消息为已压缩（不删除，保留供 UI 渲染）
        for msg in old_msgs:
            conversation_repo.delete_message_by_id(msg.id)
            conversation_repo.add_message(
                conversation_id, msg.role, make_compressed_marker(msg.content)
            )

        # 收集 DB 中所有已存在的 summary（保留，不删除）
        all_summaries = []
        for m in db_messages:
            if m.role == "system" and parse_message_content(m.content).get("type") == "summary":
                t = get_summary_text(m.content)
                if t:
                    all_summaries.append(t)

        # 写入本次新生成的 summary（不删除旧的）
        conversation_repo.add_message(conversation_id, "system", make_summary_message(summary))
        # 把新 summary 也加入列表，供内存重建时拼接
        all_summaries.append(summary)

        # 收集压缩开始时 DB 快照中所有活跃消息的文本
        # 用于重建时过滤：只有「不在这个快照中」的消息才是压缩期间新增的
        # 这样旧消息（已被压缩标记）不会通过 extra_messages 被误追加回去
        all_active_texts = set()
        for m in active_msgs:
            if m.role in ("user", "assistant"):
                all_active_texts.add(get_text_content(m.content))

        # 重建内存（传入全部摘要 + 全部活跃文本集合）
        self._rebuild_memory(conversation_id, all_summaries, recent_msgs, all_active_texts)

        logging.info(
            f"[MemoryCompressor] Compressed {len(old_msgs)} old messages "
            f"(keeping {len(recent_msgs)} recent) for conv={conversation_id[:8]}.."
        )
        return True

    def _split_messages(self, chat_msgs, rounds_to_compress: int):
        """
        将 chat_msgs 拆分为「压缩区」和「保留区」。
        按 user 消息计轮次，前 rounds_to_compress 个 user 块划为压缩区。
        """
        old_msgs = []
        recent_msgs = []
        user_count = 0
        in_recent = False

        for msg in chat_msgs:
            if msg.role == "user":
                user_count += 1
                if user_count > rounds_to_compress:
                    in_recent = True

            if in_recent:
                recent_msgs.append(msg)
            else:
                old_msgs.append(msg)

        return old_msgs, recent_msgs

    def _build_old_text(self, messages) -> str:
        """把压缩区消息拼接为便于 LLM 阅读的文本。"""
        parts = []
        for msg in messages:
            data = parse_message_content(msg.content)
            msg_type = data.get("type", "text")

            if msg.role == "user":
                text = get_text_content(msg.content)
                parts.append(f"用户：{text}")
            elif msg.role == "assistant":
                if msg_type == "agent_memory":
                    entries = get_agent_memory_content(msg.content)
                    parts.extend(entries)
                elif msg_type == "agent_workflow":
                    thought_chain = data.get("thought_chain", [])
                    for tc in thought_chain:
                        if tc.get("action") and tc.get("success"):
                            tool_name = tc["action"].get("tool", "unknown")
                            obs = tc.get("observation", "")
                            parts.append(f"Observation (tool={tool_name}): {obs}")
                    final = data.get("final_result", "")
                    if final:
                        parts.append(f"助手：{final}")
                else:
                    text = get_text_content(msg.content)
                    parts.append(f"助手：{text}")

        return "\n".join(parts)

    def _generate_summary(self, old_text: str) -> Optional[str]:
        """调用 LLM 生成摘要，使用独立 session 避免污染对话历史。"""
        from chat.model_manager import ModelManager
        try:
            prompt = COMPRESS_PROMPT.format(
                max_tokens=self.max_summary_tokens,
                conversation=old_text,
            )
            session_id = f"__compress__{id(self)}"
            summary = ModelManager().chat(
                model_name=self.compress_model,
                messages=[prompt],
                session_id=session_id,
            )
            # 清理临时 session
            mm = ModelManager()
            if session_id in mm.memory:
                del mm.memory[session_id]
            return summary.strip() if summary else None
        except Exception as e:
            logging.error(f"[MemoryCompressor] LLM summary generation failed: {e}")
            return None

    def _rebuild_memory(self, conversation_id: str, all_summaries: list, recent_db_messages, all_active_texts: set):
        """
        重建 InMemoryChatMessageHistory（调用方已持有锁）：

        步骤：
        1. 拍快照：用 all_active_texts（压缩开始时的 DB 快照）过滤
           只保留「不在快照中」的消息 → 即压缩期间新增的消息
        2. 清空内存
        3. 把全部摘要（多次压缩累积）拼接到第一条 HumanMessage 前面
        4. 注入最近保留的消息
        5. 追加步骤1中捕获的新增消息

        注意：不触碰 SystemMessage，system prompt 完全不受影响。
        """
        from chat.model_manager import ModelManager
        from langchain.schema import HumanMessage

        mm = ModelManager()
        history = mm.get_session_history(conversation_id)

        # ── 步骤 1：拍快照，只捕获「压缩期间新增」的消息 ──
        # all_active_texts 是压缩开始时 DB 中所有活跃消息的文本集合。
        # 内存中任何不在这个集合里的消息，一定是压缩期间新加入的。
        extra_messages = []
        for m in history.messages:
            if isinstance(m, HumanMessage):
                text = m.content
                # 去掉 "[历史对话摘要]\n" 前缀后再比较
                if text.startswith("[历史对话摘要]\n"):
                    text = text[len("[历史对话摘要]\n"):]
                if text not in all_active_texts:
                    extra_messages.append(m)
            elif hasattr(m, "content"):
                text = str(m.content)
                if text not in all_active_texts:
                    extra_messages.append(m)

        # ── 步骤 2：清空内存 ──
        history.clear()

        # ── 步骤 3 & 4：注入保留消息 + 全部摘要前缀 ──
        combined_summary = "\n\n---\n\n".join(all_summaries)
        injected_summary = False
        for msg in recent_db_messages:
            if msg.role == "user":
                text = get_text_content(msg.content)
                if not injected_summary:
                    # 全部摘要作为第一条 HumanMessage 的前缀
                    history.add_user_message(f"[历史对话摘要]\n{combined_summary}\n\n{text}")
                    injected_summary = True
                else:
                    history.add_user_message(text)
            elif msg.role == "assistant":
                text = get_text_content(msg.content)
                history.add_ai_message(text)

        # 如果 recent_db_messages 为空，摘要单独作为一条 HumanMessage
        if not injected_summary:
            history.add_user_message(f"[历史对话摘要]\n{combined_summary}")

        # ── 步骤 5：追加竞态期间新增的消息 ──
        for msg in extra_messages:
            if hasattr(msg, "type") and msg.type == "human":
                history.add_user_message(msg.content)
            elif hasattr(msg, "type") and msg.type == "ai":
                history.add_ai_message(msg.content)

        logging.info(
            f"[MemoryCompressor] Memory rebuilt: {len(all_summaries)} summaries + "
            f"{len(recent_db_messages)} recent + {len(extra_messages)} extra "
            f"for conv={conversation_id[:8]}.."
        )
