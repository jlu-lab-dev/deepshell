import datetime
import logging
from typing import List, Optional

from sqlalchemy.exc import SQLAlchemyError

from database.models.conversation import Conversation, Message
from database.db_manager import DatabaseManager
from utils.decorators import singleton


@singleton
class ConversationRepository:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.db_manager.create_all_tables()

    # ── Conversation CRUD ──

    def create_conversation(self, conversation_id: str, model_name: str, function_type: str) -> Optional[Conversation]:
        """创建新的会话记录"""
        with self.db_manager.session_scope() as session:
            try:
                conv = Conversation(
                    id=conversation_id,
                    model_name=model_name,
                    function_type=function_type
                )
                session.add(conv)
                session.flush()
                return conv
            except SQLAlchemyError as e:
                logging.error(f"Error creating conversation: {e}")
                return None

    def update_title(self, conversation_id: str, title: str) -> bool:
        """更新会话标题"""
        with self.db_manager.session_scope() as session:
            try:
                conv = session.query(Conversation).filter(Conversation.id == conversation_id).first()
                if conv:
                    conv.title = title
                    return True
                return False
            except SQLAlchemyError as e:
                logging.error(f"Error updating conversation title: {e}")
                return False

    def update_timestamp(self, conversation_id: str) -> bool:
        """更新会话的 updated_at 时间戳"""
        with self.db_manager.session_scope() as session:
            try:
                conv = session.query(Conversation).filter(Conversation.id == conversation_id).first()
                if conv:
                    conv.updated_at = datetime.datetime.utcnow()
                    return True
                return False
            except SQLAlchemyError as e:
                logging.error(f"Error updating conversation timestamp: {e}")
                return False

    def list_conversations(self, limit: int = 50) -> List[Conversation]:
        """返回最近 N 条会话，按 updated_at 倒序"""
        with self.db_manager.session_scope() as session:
            try:
                return session.query(Conversation)\
                    .order_by(Conversation.updated_at.desc())\
                    .limit(limit)\
                    .all()
            except SQLAlchemyError as e:
                logging.error(f"Error listing conversations: {e}")
                return []

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """获取单个会话"""
        with self.db_manager.session_scope() as session:
            try:
                return session.query(Conversation).filter(Conversation.id == conversation_id).first()
            except SQLAlchemyError as e:
                logging.error(f"Error getting conversation: {e}")
                return None

    def delete_conversation(self, conversation_id: str) -> bool:
        """级联删除会话及其所有消息"""
        with self.db_manager.session_scope() as session:
            try:
                # 先删除消息
                session.query(Message).filter(Message.conversation_id == conversation_id).delete()
                # 再删除会话
                conv = session.query(Conversation).filter(Conversation.id == conversation_id).first()
                if conv:
                    session.delete(conv)
                    return True
                return False
            except SQLAlchemyError as e:
                logging.error(f"Error deleting conversation: {e}")
                return False

    # ── Message CRUD ──

    def add_message(self, conversation_id: str, role: str, content: str) -> Optional[Message]:
        """添加一条消息"""
        with self.db_manager.session_scope() as session:
            try:
                msg = Message(
                    conversation_id=conversation_id,
                    role=role,
                    content=content
                )
                session.add(msg)
                session.flush()
                # ── 调试打印 ──────────────────────────────────────────────
                import json
                preview = content[:300] + "..." if len(content) > 300 else content
                # 尝试解析 JSON，格式化输出更友好
                try:
                    parsed = json.loads(content)
                    preview = json.dumps(parsed, ensure_ascii=False, indent=2)
                    # if len(preview) > 500:
                    #     preview = preview[:500] + "\n... (truncated)"
                except Exception:
                    pass
                print(f"\n[DB WRITE] conv={conversation_id[:8]}.. | role={role}\n{preview}\n")
                # ─────────────────────────────────────────────────────────
                return msg
            except SQLAlchemyError as e:
                logging.error(f"Error adding message: {e}")
                return None

    def get_messages(self, conversation_id: str) -> List[Message]:
        """获取某会话的所有消息，按 created_at 升序"""
        with self.db_manager.session_scope() as session:
            try:
                msgs = session.query(Message)\
                    .filter(Message.conversation_id == conversation_id)\
                    .order_by(Message.created_at.asc())\
                    .all()
                # ── 调试打印 ──────────────────────────────────────────────
                import json as _json
                print(f"\n{'='*60}")
                print(f"[DB READ] conv={conversation_id[:8]}.. | 共 {len(msgs)} 条消息")
                for i, m in enumerate(msgs):
                    print(f"\n--- 消息 #{i+1} | role={m.role} | time={m.created_at} ---")
                    try:
                        parsed = _json.loads(m.content)
                        pretty = _json.dumps(parsed, ensure_ascii=False, indent=2)
                        # if len(pretty) > 600:
                        #     pretty = pretty[:600] + "\n... (truncated)"
                    except Exception:
                        pretty = m.content[:300] + "..." if len(m.content) > 300 else m.content
                    print(pretty)
                print(f"\n{'='*60}\n")
                # ─────────────────────────────────────────────────────────
                return msgs
            except SQLAlchemyError as e:
                logging.error(f"Error getting messages: {e}")
                return []

    def delete_messages(self, conversation_id: str) -> bool:
        """删除某会话的所有消息"""
        with self.db_manager.session_scope() as session:
            try:
                session.query(Message).filter(Message.conversation_id == conversation_id).delete()
                return True
            except SQLAlchemyError as e:
                logging.error(f"Error deleting messages: {e}")
                return False
