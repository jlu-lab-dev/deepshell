import datetime
import uuid
from sqlalchemy import Column, String, Text, DateTime, Integer
from database.db_manager import Base


class Conversation(Base):
    """会话元数据表"""
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True)  # 即 session_id (UUID)
    title = Column(String(255), default="新对话")
    model_name = Column(String(64))
    function_type = Column(String(32))  # "智能问答" / "AI PPT" 等
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<Conversation(id='{self.id}', title='{self.title}')>"


class Message(Base):
    """会话消息表"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(36))
    role = Column(String(16))  # "user" / "assistant" / "system"
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<Message(id={self.id}, role='{self.role}', conversation_id='{self.conversation_id}')>"
