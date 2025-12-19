"""Base Watcher interface for all source watchers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional


class ReleaseStage(Enum):
    """Stage of a model release."""
    ANNOUNCED = "announced"      # 출시 예정 발표 (Coming soon, teaser, preview)
    LAUNCHED = "launched"        # 실제 출시 (Available, released)
    UPDATED = "updated"          # 업데이트
    UNKNOWN = "unknown"          # 알 수 없음


@dataclass
class WatchEvent:
    """Represents a detected event from any source."""
    source: str  # github, huggingface, modelscope, arxiv, news, leaderboard
    event_type: str  # new_repo, new_commit, new_release, new_model, new_paper, new_article, etc.
    model_name: str
    title: str
    description: str
    url: str
    timestamp: datetime
    extra_data: Optional[dict] = None
    release_stage: ReleaseStage = ReleaseStage.UNKNOWN  # 출시 예정 vs 실제 출시

    def to_dict(self) -> dict:
        return {
            'source': self.source,
            'event_type': self.event_type,
            'model_name': self.model_name,
            'title': self.title,
            'description': self.description,
            'url': self.url,
            'timestamp': self.timestamp.isoformat(),
            'extra_data': self.extra_data or {},
            'release_stage': self.release_stage.value,
        }

    @property
    def is_announced(self) -> bool:
        """Check if this is an announcement (not yet released)."""
        return self.release_stage == ReleaseStage.ANNOUNCED

    @property
    def is_launched(self) -> bool:
        """Check if this is an actual launch."""
        return self.release_stage == ReleaseStage.LAUNCHED


class BaseWatcher(ABC):
    """Abstract base class for all source watchers."""

    def __init__(self, model_config: dict):
        """
        Initialize the watcher with model configuration.
        
        Args:
            model_config: Dictionary containing model-specific configuration
        """
        self.model_config = model_config
        self.model_name = model_config.get('name', 'Unknown')

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the name of this source (e.g., 'github', 'huggingface')."""
        pass

    @abstractmethod
    def check_updates(self, last_check_state: Optional[dict]) -> tuple[List[WatchEvent], dict]:
        """
        Check for updates since the last check.
        
        Args:
            last_check_state: State from the previous check (source-specific)
            
        Returns:
            Tuple of (list of new events, new state to save)
        """
        pass

    def get_state_key(self) -> str:
        """Return a unique key for storing this watcher's state."""
        return f"{self.source_name}:{self.model_name}"

