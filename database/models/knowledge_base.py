from sqlalchemy import Column, Integer, String, DateTime, Text, Float
from database.db_manager import Base

import datetime
import uuid

class KnowledgeBase(Base):
    """Knowledge base metadata entity"""
    __tablename__ = 'knowledge_bases'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    embedding_model = Column(String(100), nullable=False)
    collection_name = Column(String(255), nullable=False)
    persist_directory = Column(String(512), nullable=False)
    document_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    chunk_size = Column(Integer, nullable=False)
    chunk_overlap = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f"<KnowledgeBase(id='{self.id}', name='{self.name}', document_count={self.document_count})>"


class Document(Base):
    """Document entity"""
    __tablename__ = 'documents'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kb_id = Column(String(36), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_type = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    chunk_count = Column(Integer, default=0)
    status = Column(String(20), default='active')
    
    def __repr__(self):
        return f"<Document(id='{self.id}', filename='{self.filename}', kb_id='{self.kb_id}')>"
