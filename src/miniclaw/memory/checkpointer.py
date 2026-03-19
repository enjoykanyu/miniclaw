"""
MiniClaw MySQL Checkpointer
Provides persistent state storage using MySQL
"""

from typing import Optional, Any, Dict
from datetime import datetime

from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from miniclaw.config.settings import settings


Base = declarative_base()


class CheckpointModel(Base):
    __tablename__ = "checkpoints"
    
    thread_id = Column(String(255), primary_key=True)
    checkpoint_id = Column(String(255), primary_key=True)
    metadata = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class MySQLSaver(BaseCheckpointSaver):
    def __init__(self, connection_string: Optional[str] = None):
        self.connection_string = connection_string or settings.mysql_url_sync
        self.engine = create_engine(self.connection_string)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
    
    def get(self, config: Dict[str, Any]) -> Optional[Any]:
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        checkpoint_id = config.get("configurable", {}).get("checkpoint_id")
        
        if not checkpoint_id:
            return None
        
        session = self.Session()
        try:
            row = session.query(CheckpointModel).filter_by(
                thread_id=thread_id,
                checkpoint_id=checkpoint_id,
            ).first()
            
            if row and row.metadata:
                import json
                return json.loads(row.metadata)
            
            return None
        finally:
            session.close()
    
    def put(self, config: Dict[str, Any], checkpoint: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        checkpoint_id = checkpoint.get("id", str(datetime.now().timestamp()))
        
        import json
        checkpoint_json = json.dumps(checkpoint, default=str)
        metadata_json = json.dumps(metadata, default=str) if metadata else None
        
        session = self.Session()
        try:
            existing = session.query(CheckpointModel).filter_by(
                thread_id=thread_id,
                checkpoint_id=checkpoint_id,
            ).first()
            
            if existing:
                existing.metadata = checkpoint_json
            else:
                new_checkpoint = CheckpointModel(
                    thread_id=thread_id,
                    checkpoint_id=checkpoint_id,
                    metadata=checkpoint_json,
                )
                session.add(new_checkpoint)
            
            session.commit()
        finally:
            session.close()
    
    def list(self, config: Dict[str, Any], limit: int = 10) -> list:
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        
        session = self.Session()
        try:
            rows = session.query(CheckpointModel).filter_by(
                thread_id=thread_id,
            ).order_by(CheckpointModel.created_at.desc()).limit(limit).all()
            
            return [
                {
                    "thread_id": row.thread_id,
                    "checkpoint_id": row.checkpoint_id,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ]
        finally:
            session.close()


def create_checkpointer(checkpoint_type: str = "memory") -> BaseCheckpointSaver:
    if checkpoint_type == "mysql":
        return MySQLSaver()
    elif checkpoint_type == "sqlite":
        from langgraph.checkpoint.sqlite import SqliteSaver
        import sqlite3
        conn = sqlite3.connect("data/checkpoints.db")
        return SqliteSaver(conn)
    else:
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()
