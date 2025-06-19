from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
import os
from pathlib import Path
import logging
from contextlib import contextmanager
from utils.decorators import singleton


# 所有实体类需要继承这个类
Base = declarative_base()

@singleton
class DatabaseManager:
    """Centralized database connection manager"""
    
    def __init__(self, db_path=None, echo=False):
        """Initialize database connection
        
        Args:
            db_path: Path to SQLite database file. If None, a default path will be used.
            echo: If True, SQL statements will be logged.
        """
        if not db_path:
            # Default database location
            base_dir = Path(os.path.expanduser("~/.deepshell-ai/database"))
            base_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(base_dir / "deepshell_ai.db")
        
        self.db_path = db_path
        self.engine = create_engine(f'sqlite:///{db_path}', echo=echo)
        
        """
        TODO: expire_on_commit = False 可能会有内存泄露问题
            不使用 False 时需要改造 repository 映射创建 DTO 返回，按当前形式返回时 session 已关闭无法访问
        """
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.Session = scoped_session(self.session_factory)
        
        logging.info(f"Database initialized at {db_path}")
    
    def create_all_tables(self):
        """Create all tables defined in Base"""
        Base.metadata.create_all(self.engine)
        logging.info("All database tables created")
    
    def drop_all_tables(self):
        """Drop all tables defined in Base"""
        Base.metadata.drop_all(self.engine)
        logging.info("All database tables dropped")
    
    def get_session(self):
        """Get a new session"""
        return self.Session()
    
    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations"""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logging.error(f"Database transaction error: {str(e)}")
            raise
        finally:
            session.close()
