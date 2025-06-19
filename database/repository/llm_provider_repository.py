from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
import logging
from typing import List, Optional, Dict, Any

from database.models.llm_provider import LLMProvider
from database.db_manager import DatabaseManager
from utils.decorators import singleton

@singleton
class LLMProviderRepository:
    def __init__(self):
        # Use the centralized database manager
        self.db_manager = DatabaseManager()
        # Make sure tables are created
        self.db_manager.create_all_tables()
        # Initialize default providers on startup
        self.initialize_default_providers()
        
    def create_provider(self, provider_data: Dict[str, Any]) -> Optional[LLMProvider]:
        """Create a new LLM provider entry"""
        with self.db_manager.session_scope() as session:
            try:
                provider = LLMProvider(**provider_data)
                session.add(provider)
                session.flush()  # Flush to get the generated ID
                return provider
            except SQLAlchemyError as e:
                logging.error(f"Error creating LLM provider: {str(e)}")
                return None
                
    def update_provider(self, provider_id: str, provider_data: Dict[str, Any]) -> bool:
        """Update LLM provider metadata"""
        with self.db_manager.session_scope() as session:
            try:
                session.execute(
                    update(LLMProvider)
                    .where(LLMProvider.id == provider_id)
                    .values(**provider_data)
                )
                return True
            except SQLAlchemyError as e:
                logging.error(f"Error updating LLM provider: {str(e)}")
                return False
    
    def get_provider(self, provider_id: str) -> Optional[LLMProvider]:
        """Get LLM provider by ID"""
        with self.db_manager.session_scope() as session:
            try:
                return session.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
            except SQLAlchemyError as e:
                logging.error(f"Error fetching LLM provider: {str(e)}")
                return None
                
    def get_provider_by_name(self, name: str) -> Optional[LLMProvider]:
        """Get LLM provider by name"""
        with self.db_manager.session_scope() as session:
            try:
                return session.query(LLMProvider).filter(LLMProvider.name == name).first()
            except SQLAlchemyError as e:
                logging.error(f"Error fetching LLM provider: {str(e)}")
                return None
                
    def list_providers(self, active_only: bool = False) -> List[LLMProvider]:
        """List all LLM providers, optionally filtering for active ones only"""
        with self.db_manager.session_scope() as session:
            try:
                query = session.query(LLMProvider)
                if active_only:
                    query = query.filter(LLMProvider.is_active == True)
                return query.all()
            except SQLAlchemyError as e:
                logging.error(f"Error listing LLM providers: {str(e)}")
                return []
                
    def delete_provider(self, provider_id: str) -> bool:
        """Delete an LLM provider"""
        with self.db_manager.session_scope() as session:
            try:
                provider = session.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
                if provider:
                    session.delete(provider)
                    return True
                return False
            except SQLAlchemyError as e:
                logging.error(f"Error deleting LLM provider: {str(e)}")
                return False
    
    def initialize_default_providers(self) -> bool:
        """Initialize the database with default LLM providers if they don't exist"""
        try:
            # Check if providers already exist
            providers = self.list_providers()
            if providers:
                logging.info(f"Found {len(providers)} existing LLM providers, skipping initialization")
                return True
                

            # Define default providers
            deepseek = {
                "name": "Deepseek 官方",
                "description": "Deepseeker LLM Provider",
                "base_url": "https://api.deepseeker.com",
                "api_key": "your_api_key_here",
                "is_active": True,
                "default_parameters": {},
            }
            alibaba_bailian = {
                "name": "阿里云百炼平台",
                "description": "Alibaba Bailian Provider",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "api_key": "your_api_key_here",
                "is_active": True,
                "default_parameters": {},
            }
            
            ollama = {
                "name": "Ollama",
                "description": "Ollama LLM Provider",
                "base_url": "http://localhost:11434",
                "api_key": None,
                "is_active": True,
                "default_parameters": {},
            }
            
            # Create default providers
            self.create_provider(deepseek)
            self.create_provider(alibaba_bailian)
            self.create_provider(ollama)
            
            logging.info("Default LLM providers initialized")
            return True
            
        except Exception as e:
            logging.error(f"Error initializing default LLM providers: {str(e)}")
            return False


if __name__ == "__main__":
    # Example usage
    repo = LLMProviderRepository()
    
    
    # List all providers
    providers = repo.list_providers()
    for provider in providers:
        print(f"Provider: {provider.name}, Active: {provider.is_active}, Models: {provider.available_models}")
