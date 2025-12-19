"""Hugging Face Watcher - monitors Hugging Face Hub for model updates."""

from datetime import datetime
from typing import List, Optional
import requests

from .base import BaseWatcher, WatchEvent


class HuggingFaceWatcher(BaseWatcher):
    """Watcher for Hugging Face Hub model updates."""

    API_BASE = "https://huggingface.co/api"

    def __init__(self, model_config: dict, hf_token: Optional[str] = None):
        super().__init__(model_config)
        self.model_id = model_config.get('huggingface')
        self.token = hf_token
        self._headers = self._build_headers()

    def _build_headers(self) -> dict:
        headers = {
            'User-Agent': 'AI-Model-Release-Watcher'
        }
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        return headers

    @property
    def source_name(self) -> str:
        return 'huggingface'

    def check_updates(self, last_check_state: Optional[dict]) -> tuple[List[WatchEvent], dict]:
        """Check for model updates on Hugging Face Hub."""
        if not self.model_id:
            return [], last_check_state or {}

        events = []
        new_state = last_check_state.copy() if last_check_state else {}

        # Check model info
        model_event, new_state = self._check_model(new_state)
        if model_event:
            events.append(model_event)

        # Check for new commits/updates
        commit_events, new_state = self._check_commits(new_state)
        events.extend(commit_events)

        return events, new_state

    def _check_model(self, state: dict) -> tuple[Optional[WatchEvent], dict]:
        """Check if the model exists and get its info."""
        if state.get('model_known'):
            return None, state

        try:
            url = f"{self.API_BASE}/models/{self.model_id}"
            response = requests.get(url, headers=self._headers, timeout=30)
            
            if response.status_code == 200:
                model_data = response.json()
                state['model_known'] = True
                state['model_id'] = model_data.get('id')
                
                # Parse created_at or lastModified
                created_at = model_data.get('createdAt') or model_data.get('lastModified')
                if created_at:
                    try:
                        timestamp = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        timestamp = datetime.utcnow()
                else:
                    timestamp = datetime.utcnow()

                return WatchEvent(
                    source='huggingface',
                    event_type='new_model',
                    model_name=self.model_name,
                    title=f"Model discovered: {self.model_id}",
                    description=model_data.get('description', '')[:300] or f"Pipeline: {model_data.get('pipeline_tag', 'N/A')}",
                    url=f"https://huggingface.co/{self.model_id}",
                    timestamp=timestamp,
                    extra_data={
                        'downloads': model_data.get('downloads', 0),
                        'likes': model_data.get('likes', 0),
                        'pipeline_tag': model_data.get('pipeline_tag'),
                        'tags': model_data.get('tags', [])[:5],
                    }
                ), state
            elif response.status_code == 404:
                # Model doesn't exist yet, keep checking
                pass
        except requests.RequestException:
            pass

        return None, state

    def _check_commits(self, state: dict) -> tuple[List[WatchEvent], dict]:
        """Check for new commits/updates to the model."""
        events = []
        last_commit_id = state.get('last_commit_id')

        try:
            url = f"{self.API_BASE}/models/{self.model_id}/commits/main"
            response = requests.get(url, headers=self._headers, timeout=30)
            
            if response.status_code == 200:
                commits = response.json()
                if commits and isinstance(commits, list) and len(commits) > 0:
                    latest_commit = commits[0]
                    latest_id = latest_commit.get('id') or latest_commit.get('sha')
                    
                    if last_commit_id and latest_id and latest_id != last_commit_id:
                        # Find new commits
                        new_commits = []
                        for commit in commits:
                            commit_id = commit.get('id') or commit.get('sha')
                            if commit_id == last_commit_id:
                                break
                            new_commits.append(commit)
                        
                        for commit in new_commits[:5]:
                            commit_date = commit.get('date') or commit.get('createdAt')
                            try:
                                timestamp = datetime.fromisoformat(commit_date.replace('Z', '+00:00'))
                            except (ValueError, AttributeError, TypeError):
                                timestamp = datetime.utcnow()

                            events.append(WatchEvent(
                                source='huggingface',
                                event_type='new_commit',
                                model_name=self.model_name,
                                title=commit.get('title', 'Update')[:100],
                                description=f"Author: {commit.get('author', {}).get('name', 'Unknown')}",
                                url=f"https://huggingface.co/{self.model_id}/commit/{commit.get('id', '')}",
                                timestamp=timestamp,
                                extra_data={
                                    'commit_id': (commit.get('id') or '')[:7],
                                }
                            ))
                    
                    if latest_id:
                        state['last_commit_id'] = latest_id
        except requests.RequestException:
            pass

        return events, state

