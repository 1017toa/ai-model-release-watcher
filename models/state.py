"""State management using SQLite for tracking last checked states."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, Column, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class WatcherState(Base):
    """SQLAlchemy model for storing watcher states."""
    __tablename__ = 'watcher_states'

    key = Column(String(255), primary_key=True)
    state_json = Column(Text, nullable=False, default='{}')
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_state(self) -> dict:
        """Deserialize the state JSON."""
        try:
            return json.loads(self.state_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_state(self, state: dict):
        """Serialize the state to JSON."""
        self.state_json = json.dumps(state, default=str)


class StateManager:
    """Manager for watcher states using SQLite."""

    def __init__(self, database_path: str = 'watcher_state.db'):
        """
        Initialize the state manager.
        
        Args:
            database_path: Path to the SQLite database file
        """
        self.database_path = database_path
        self.engine = create_engine(f'sqlite:///{database_path}')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def get_state(self, key: str) -> Optional[dict]:
        """
        Get the state for a specific watcher key.
        
        Args:
            key: Unique key for the watcher (e.g., 'github:Z-Image')
            
        Returns:
            State dictionary or None if not found
        """
        session = self.Session()
        try:
            state = session.query(WatcherState).filter_by(key=key).first()
            return state.get_state() if state else None
        finally:
            session.close()

    def save_state(self, key: str, state: dict):
        """
        Save the state for a specific watcher key.
        
        Args:
            key: Unique key for the watcher
            state: State dictionary to save
        """
        session = self.Session()
        try:
            existing = session.query(WatcherState).filter_by(key=key).first()
            if existing:
                existing.set_state(state)
                existing.last_updated = datetime.utcnow()
            else:
                new_state = WatcherState(key=key)
                new_state.set_state(state)
                session.add(new_state)
            session.commit()
        finally:
            session.close()

    def get_last_updated(self, key: str) -> Optional[datetime]:
        """
        Get the last updated timestamp for a watcher.
        
        Args:
            key: Unique key for the watcher
            
        Returns:
            Last updated datetime or None
        """
        session = self.Session()
        try:
            state = session.query(WatcherState).filter_by(key=key).first()
            return state.last_updated if state else None
        finally:
            session.close()

    def clear_state(self, key: str):
        """
        Clear the state for a specific watcher key.
        
        Args:
            key: Unique key for the watcher
        """
        session = self.Session()
        try:
            session.query(WatcherState).filter_by(key=key).delete()
            session.commit()
        finally:
            session.close()

    def clear_all_states(self):
        """Clear all watcher states."""
        session = self.Session()
        try:
            session.query(WatcherState).delete()
            session.commit()
        finally:
            session.close()

    def list_all_keys(self) -> list:
        """
        List all stored state keys.
        
        Returns:
            List of all keys
        """
        session = self.Session()
        try:
            states = session.query(WatcherState.key).all()
            return [s.key for s in states]
        finally:
            session.close()

