import uuid
from sqlalchemy import Column, String, Boolean, JSON
from database.db_manager import Base

class LLMProvider(Base):
    """LLM Provider model representing different LLM service providers"""
    __tablename__ = 'llm_providers'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(500), nullable=True)
    base_url = Column(String(255), nullable=True)
    api_key = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    default_parameters = Column(JSON, nullable=True)
    available_models = Column(JSON, nullable=True)
    
    def __repr__(self):
        return f"<LlmProvider(id='{self.id}', name='{self.name}')>"