from pydoc import doc
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
import logging
from typing import List, Optional, Dict, Any

from database.models.knowledge_base import KnowledgeBase, Document
from database.db_manager import DatabaseManager
from utils.decorators import singleton

@singleton
class KnowledgeBaseRepository:
    def __init__(self):
        # Use the centralized database manager
        self.db_manager = DatabaseManager()
        # Make sure tables are created
        self.db_manager.create_all_tables()

    def create_knowledge_base(self, kb_data: Dict[str, Any]) -> Optional[KnowledgeBase]:
        """Create a new knowledge base entry"""
        with self.db_manager.session_scope() as session:
            try:
                kb = KnowledgeBase(**kb_data)
                session.add(kb)
                session.flush()  # Flush to get the generated ID
                return kb
            except SQLAlchemyError as e:
                logging.error(f"Error creating knowledge base: {str(e)}")
                return None

    def update_knowledge_base(self, kb_id: str, kb_data: Dict[str, Any]) -> bool:
        """Update knowledge base metadata"""
        with self.db_manager.session_scope() as session:
            try:
                session.execute(
                    update(KnowledgeBase)
                    .where(KnowledgeBase.id == kb_id)
                    .values(**kb_data)
                )
                return True
            except SQLAlchemyError as e:
                logging.error(f"Error updating knowledge base: {str(e)}")
                return False
            
    def get_knowledge_base(self, kb_id: str) -> Optional[KnowledgeBase]:
        """Get knowledge base by ID"""
        with self.db_manager.session_scope() as session:
            try:
                return session.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
            except SQLAlchemyError as e:
                logging.error(f"Error fetching knowledge base: {str(e)}")
                return None
            
    def get_knowledge_base_by_collection(self, collection_name: str) -> Optional[KnowledgeBase]:
        """Get knowledge base by collection name"""
        with self.db_manager.session_scope() as session:
            try:
                return session.query(KnowledgeBase).filter(KnowledgeBase.collection_name == collection_name).first()
            except SQLAlchemyError as e:
                logging.error(f"Error fetching knowledge base: {str(e)}")
                return None
            
    def list_knowledge_bases(self) -> List[KnowledgeBase]:
        """List all knowledge bases"""
        with self.db_manager.session_scope() as session:
            try:
                return session.query(KnowledgeBase).all()
            except SQLAlchemyError as e:
                logging.error(f"Error listing knowledge bases: {str(e)}")
                return []
            
    def delete_knowledge_base(self, kb_id: str) -> bool:
        """Delete a knowledge base"""
        with self.db_manager.session_scope() as session:
            try:
                kb = session.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
                if kb:
                    session.delete(kb)
                    return True
                return False
            except SQLAlchemyError as e:
                logging.error(f"Error deleting knowledge base: {str(e)}")
                return False
            
    def increment_document_count(self, kb_id: str, increment: int = 1) -> bool:
        """Increment document count for a knowledge base"""
        with self.db_manager.session_scope() as session:
            try:
                kb = session.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
                if kb:
                    kb.document_count += increment
                    return True
                return False
            except SQLAlchemyError as e:
                logging.error(f"Error incrementing document count: {str(e)}")
                return False
            
    def increment_chunk_count(self, kb_id: str, increment: int = 1) -> bool:
        """Increment chunk count for a knowledge base"""
        with self.db_manager.session_scope() as session:
            try:
                kb = session.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
                if kb:
                    kb.chunk_count += increment
                    return True
                return False
            except SQLAlchemyError as e:
                logging.error(f"Error incrementing chunk count: {str(e)}")
                return False
            
    # Document operations
    def add_document(self, doc_data: Dict[str, Any]) -> Optional[Document]:
        """Add a document to the knowledge base"""
        with self.db_manager.session_scope() as session:
            try:
                doc = Document(**doc_data)
                session.add(doc)
                # Increment document count in the knowledge base
                kb = session.query(KnowledgeBase).filter(KnowledgeBase.id == doc_data['kb_id']).first()
                if kb:
                    kb.document_count += 1
                session.flush()  # Flush to get the generated ID
                return doc
            except SQLAlchemyError as e:
                logging.error(f"Error adding document: {str(e)}")
                return None

    def get_document_by_id(self, doc_id: str) -> Optional[Document]:
        """Get a document by its ID"""
        with self.db_manager.session_scope() as session:
            try:
                return session.query(Document).filter(Document.id == doc_id).first()
            except SQLAlchemyError as e:
                logging.error(f"Error fetching document: {str(e)}")
                return None
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the knowledge base"""
        with self.db_manager.session_scope() as session:
            try:
                doc = session.query(Document).filter(Document.id == doc_id).first()
                if doc:
                    session.delete(doc)
                    # Decrement document count in the knowledge base
                    kb = session.query(KnowledgeBase).filter(KnowledgeBase.id == doc.kb_id).first()
                    if kb:
                        kb.document_count -= 1
                    return True
                return False
            except SQLAlchemyError as e:
                logging.error(f"Error deleting document: {str(e)}")
                return False
            
    def get_documents_by_kb(self, kb_id: str) -> List[Document]:
        """Get all documents for a knowledge base"""
        with self.db_manager.session_scope() as session:
            try:
                return session.query(Document).filter(Document.kb_id == kb_id).all()
            except SQLAlchemyError as e:
                logging.error(f"Error fetching documents: {str(e)}")
                return []
            
    def update_document_chunks(self, doc_id: str, chunk_count: int) -> bool:
        """Update chunk count for a document"""
        with self.db_manager.session_scope() as session:
            try:
                doc = session.query(Document).filter(Document.id == doc_id).first()
                if doc:
                    # Calculate the difference in chunks
                    diff = chunk_count - doc.chunk_count
                    doc.chunk_count = chunk_count
                    
                    # Update the knowledge base chunk count as well
                    kb = session.query(KnowledgeBase).filter(KnowledgeBase.id == doc.kb_id).first()
                    if kb:
                        kb.chunk_count += diff
                    
                    return True
                return False
            except SQLAlchemyError as e:
                logging.error(f"Error updating document chunks: {str(e)}")
                return False


if __name__ == "__main__":
    # Example usage
    repo = KnowledgeBaseRepository()
    
    # Create a new knowledge base
    kb_data = {
        'name': 'Test KB',
        'description': 'This is a test knowledge base.',
        'embedding_model': 'test_model',
        'collection_name': 'test_collection',
        'persist_directory': '/path/to/directory',
        'chunk_size': 512,
        'chunk_overlap': 50
    }
    
    kb = repo.create_knowledge_base(kb_data)
    print(f"Created KB: {kb}")


    doc_data = {
        'kb_id': kb.id,
        'filename': 'test_doc.txt',
        'file_path': '/path/to/test_doc.txt',
        'file_type': 'txt'
    }
    doc = repo.add_document(doc_data)
    print(f"Added Document: {doc}")
    # List all knowledge bases
    # kbs = repo.list_knowledge_bases()
    # print(f"All KBs: {kbs}")