"""ModelScope Watcher - monitors ModelScope for model updates."""

from datetime import datetime
from typing import List, Optional
import requests

from .base import BaseWatcher, WatchEvent


class ModelScopeWatcher(BaseWatcher):
    """Watcher for ModelScope model updates."""

    API_BASE = "https://modelscope.cn/api/v1"

    def __init__(self, model_config: dict):
        super().__init__(model_config)
        self.model_id = model_config.get('modelscope')

    @property
    def source_name(self) -> str:
        return 'modelscope'

    def check_updates(self, last_check_state: Optional[dict]) -> tuple[List[WatchEvent], dict]:
        """Check for model updates on ModelScope."""
        if not self.model_id:
            return [], last_check_state or {}

        events = []
        new_state = last_check_state.copy() if last_check_state else {}

        # Check model info
        model_event, new_state = self._check_model(new_state)
        if model_event:
            events.append(model_event)

        return events, new_state

    def _check_model(self, state: dict) -> tuple[Optional[WatchEvent], dict]:
        """Check if the model exists on ModelScope."""
        if state.get('model_known'):
            # Check for updates by comparing last_modified
            return self._check_model_updates(state)

        try:
            # ModelScope API format: owner/model_name
            url = f"{self.API_BASE}/models/{self.model_id}"
            headers = {
                'User-Agent': 'AI-Model-Release-Watcher',
                'Accept': 'application/json',
            }
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('Success') or data.get('Code') == 200:
                    model_data = data.get('Data', {})
                    state['model_known'] = True
                    state['last_modified'] = model_data.get('LastModifiedTime') or model_data.get('GmtModified')
                    
                    # Parse timestamp
                    created_time = model_data.get('GmtCreate') or model_data.get('CreatedTime')
                    try:
                        if created_time:
                            if isinstance(created_time, (int, float)):
                                timestamp = datetime.fromtimestamp(created_time / 1000)
                            else:
                                timestamp = datetime.fromisoformat(str(created_time).replace('Z', '+00:00'))
                        else:
                            timestamp = datetime.utcnow()
                    except (ValueError, TypeError):
                        timestamp = datetime.utcnow()

                    return WatchEvent(
                        source='modelscope',
                        event_type='new_model',
                        model_name=self.model_name,
                        title=f"Model discovered: {self.model_id}",
                        description=model_data.get('ChineseDescription') or model_data.get('Description', '')[:300],
                        url=f"https://modelscope.cn/models/{self.model_id}",
                        timestamp=timestamp,
                        extra_data={
                            'downloads': model_data.get('Downloads', 0),
                            'likes': model_data.get('Likes', 0),
                            'task': model_data.get('Task'),
                        }
                    ), state
        except requests.RequestException:
            pass

        return None, state

    def _check_model_updates(self, state: dict) -> tuple[Optional[WatchEvent], dict]:
        """Check for updates to an existing model."""
        try:
            url = f"{self.API_BASE}/models/{self.model_id}"
            headers = {
                'User-Agent': 'AI-Model-Release-Watcher',
                'Accept': 'application/json',
            }
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('Success') or data.get('Code') == 200:
                    model_data = data.get('Data', {})
                    new_last_modified = model_data.get('LastModifiedTime') or model_data.get('GmtModified')
                    old_last_modified = state.get('last_modified')
                    
                    if new_last_modified and old_last_modified and new_last_modified != old_last_modified:
                        state['last_modified'] = new_last_modified
                        
                        try:
                            if isinstance(new_last_modified, (int, float)):
                                timestamp = datetime.fromtimestamp(new_last_modified / 1000)
                            else:
                                timestamp = datetime.fromisoformat(str(new_last_modified).replace('Z', '+00:00'))
                        except (ValueError, TypeError):
                            timestamp = datetime.utcnow()

                        return WatchEvent(
                            source='modelscope',
                            event_type='new_commit',
                            model_name=self.model_name,
                            title=f"Model updated: {self.model_id}",
                            description="The model has been updated on ModelScope",
                            url=f"https://modelscope.cn/models/{self.model_id}",
                            timestamp=timestamp,
                            extra_data={
                                'downloads': model_data.get('Downloads', 0),
                            }
                        ), state
                    
                    state['last_modified'] = new_last_modified
        except requests.RequestException:
            pass

        return None, state

