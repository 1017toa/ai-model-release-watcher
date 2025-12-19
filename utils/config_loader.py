"""Configuration loader utility."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Set

import yaml


@dataclass
class ModelConfig:
    """Configuration for a single model to monitor."""
    name: str
    github: Optional[str] = None
    huggingface: Optional[str] = None
    modelscope: Optional[str] = None
    arxiv_query: Optional[str] = None
    news_keywords: Optional[str] = None
    # Priority level: 'high' means notify on every change
    priority: str = 'normal'
    # Event types to always notify for this model
    always_notify: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> 'ModelConfig':
        return cls(
            name=data.get('name', 'Unknown'),
            github=data.get('github'),
            huggingface=data.get('huggingface'),
            modelscope=data.get('modelscope'),
            arxiv_query=data.get('arxiv_query'),
            news_keywords=data.get('news_keywords'),
            priority=data.get('priority', 'normal'),
            always_notify=data.get('always_notify', []),
        )

    @property
    def is_high_priority(self) -> bool:
        return self.priority.lower() == 'high'


@dataclass
class PriorityModelConfig:
    """Configuration for priority model notifications."""
    name: str
    notify_all_commits: bool = True
    notify_all_hf_changes: bool = True
    mention_channel: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> 'PriorityModelConfig':
        return cls(
            name=data.get('name', ''),
            notify_all_commits=data.get('notify_all_commits', True),
            notify_all_hf_changes=data.get('notify_all_hf_changes', True),
            mention_channel=data.get('mention_channel', True),
        )


@dataclass
class LeaderboardConfig:
    """
    Configuration for leaderboard monitoring.
    
    Available boards (Artificial Analysis API):
    - text-to-image: Text-to-Image models
    - image-editing: Image Editing models
    - text-to-video: Text-to-Video models
    - image-to-video: Image-to-Video models
    - text-to-speech: Text-to-Speech models
    """
    enabled: bool = True
    # 활성화된 리더보드 목록
    boards: List[str] = field(default_factory=lambda: [
        'text-to-image', 'image-editing',
        'text-to-video', 'image-to-video',
        'text-to-speech',
    ])
    # 각 리더보드별 활성화 상태 (config에서 개별 on/off 용)
    board_settings: Dict[str, bool] = field(default_factory=lambda: {
        'text-to-image': True,
        'image-editing': True,
        'text-to-video': True,
        'image-to-video': True,
        'text-to-speech': True,
    })
    # 모니터링할 최대 순위 (기본값: 30등 이내)
    max_rank: int = 30
    urls: Dict[str, str] = field(default_factory=lambda: {
        'text-to-image': 'https://artificialanalysis.ai/image/leaderboard/text-to-image',
        'image-editing': 'https://artificialanalysis.ai/image/leaderboard/editing',
        'text-to-video': 'https://artificialanalysis.ai/video/leaderboard/text-to-video',
        'image-to-video': 'https://artificialanalysis.ai/video/leaderboard/image-to-video',
        'text-to-speech': 'https://artificialanalysis.ai/speech/leaderboard/text-to-speech',
    })

    @classmethod
    def from_dict(cls, data: dict) -> 'LeaderboardConfig':
        if not data:
            return cls()
        
        default_board_settings = {
            'text-to-image': True,
            'image-editing': True,
            'text-to-video': True,
            'image-to-video': True,
            'text-to-speech': True,
        }
        default_urls = {
            'text-to-image': 'https://artificialanalysis.ai/image/leaderboard/text-to-image',
            'image-editing': 'https://artificialanalysis.ai/image/leaderboard/editing',
            'text-to-video': 'https://artificialanalysis.ai/video/leaderboard/text-to-video',
            'image-to-video': 'https://artificialanalysis.ai/video/leaderboard/image-to-video',
            'text-to-speech': 'https://artificialanalysis.ai/speech/leaderboard/text-to-speech',
        }
        
        # boards 설정 처리: dict 형식 (새로운 형식) 또는 list 형식 (이전 형식) 지원
        boards_config = data.get('boards', default_board_settings)
        
        if isinstance(boards_config, dict):
            # 새로운 형식: { 'text-to-image': true, 'image-editing': false, ... }
            board_settings = {**default_board_settings, **boards_config}
            # True인 보드만 활성화
            enabled_boards = [board for board, enabled in board_settings.items() if enabled]
        elif isinstance(boards_config, list):
            # 이전 형식: ['text-to-image', 'image-editing', ...]
            enabled_boards = boards_config
            board_settings = {board: (board in enabled_boards) for board in default_board_settings}
        else:
            enabled_boards = list(default_board_settings.keys())
            board_settings = default_board_settings
        
        return cls(
            enabled=data.get('enabled', True),
            boards=enabled_boards,
            board_settings=board_settings,
            max_rank=data.get('max_rank', 30),
            urls=data.get('urls', default_urls),
        )


@dataclass
class NotificationConfig:
    """Notification settings."""
    include_icons: bool = True
    include_timestamp: bool = True
    mention_channel_for: List[str] = field(default_factory=lambda: ['new_release', 'new_model', 'release_launched'])
    event_routing: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> 'NotificationConfig':
        return cls(
            include_icons=data.get('include_icons', True),
            include_timestamp=data.get('include_timestamp', True),
            mention_channel_for=data.get('mention_channel_for', ['new_release', 'new_model', 'release_launched']),
            event_routing=data.get('event_routing', {}),
        )


@dataclass
class Config:
    """Main configuration class."""
    slack_webhook_url: str
    check_interval_hours: int
    database_path: str
    models: List[ModelConfig]
    notifications: NotificationConfig
    leaderboards: LeaderboardConfig
    priority_models: List[PriorityModelConfig] = field(default_factory=list)
    slack_channels: Dict[str, str] = field(default_factory=dict)
    github_token: Optional[str] = None
    huggingface_token: Optional[str] = None
    artificial_analysis_api_key: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> 'Config':
        models = [ModelConfig.from_dict(m) for m in data.get('models', [])]
        notifications = NotificationConfig.from_dict(data.get('notifications', {}))
        leaderboards = LeaderboardConfig.from_dict(data.get('leaderboards', {}))
        priority_models = [PriorityModelConfig.from_dict(p) for p in data.get('priority_models', [])]
        
        # Load Slack webhooks from environment variables (priority) or config file
        slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL') or data.get('slack_webhook_url', '')
        
        # Load channel-specific webhooks from environment variables
        slack_channels = {}
        slack_channels['leaderboard'] = os.environ.get('SLACK_WEBHOOK_LEADERBOARD') or data.get('slack_channels', {}).get('leaderboard', '')
        slack_channels['announcements'] = os.environ.get('SLACK_WEBHOOK_ANNOUNCEMENTS') or data.get('slack_channels', {}).get('announcements', '')
        slack_channels['launches'] = os.environ.get('SLACK_WEBHOOK_LAUNCHES') or data.get('slack_channels', {}).get('launches', '')
        
        # Remove empty channel webhooks
        slack_channels = {k: v for k, v in slack_channels.items() if v}
        
        # Merge event routing from notifications into slack_channels
        channel_webhooks = slack_channels.copy()
        for event_type, channel_name in notifications.event_routing.items():
            if channel_name in slack_channels:
                channel_webhooks[event_type] = slack_channels[channel_name]
        
        return cls(
            slack_webhook_url=slack_webhook_url,
            check_interval_hours=data.get('check_interval_hours', 1),
            database_path=data.get('database_path', 'data/watcher_state.db'),
            models=models,
            notifications=notifications,
            leaderboards=leaderboards,
            priority_models=priority_models,
            slack_channels=channel_webhooks,
            # API tokens are loaded from environment variables only (for security)
            github_token=os.environ.get('GITHUB_TOKEN'),
            huggingface_token=os.environ.get('HF_TOKEN'),
            artificial_analysis_api_key=os.environ.get('ARTIFICIAL_ANALYSIS_API_KEY'),
        )

    def get_channel_webhook(self, channel_name: str) -> str:
        """Get webhook URL for a specific channel."""
        return self.slack_channels.get(channel_name, self.slack_webhook_url)

    def get_priority_config(self, model_name: str) -> Optional[PriorityModelConfig]:
        """Get priority configuration for a model."""
        for pm in self.priority_models:
            if pm.name.lower() == model_name.lower():
                return pm
        return None

    def is_priority_model(self, model_name: str) -> bool:
        """Check if a model is configured as priority."""
        # Check in priority_models list
        if self.get_priority_config(model_name):
            return True
        # Check in model config
        for model in self.models:
            if model.name.lower() == model_name.lower() and model.is_high_priority:
                return True
        return False

    def get_priority_model_names(self) -> Set[str]:
        """Get set of all priority model names."""
        names = set()
        for pm in self.priority_models:
            names.add(pm.name.lower())
        for model in self.models:
            if model.is_high_priority:
                names.add(model.name.lower())
        return names


def load_config(config_path: str = 'config.yaml') -> Config:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Config object with all settings
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid
    """
    path = Path(config_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    if data is None:
        data = {}
    
    return Config.from_dict(data)
