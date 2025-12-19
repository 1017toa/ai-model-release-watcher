"""Leaderboard Watcher - monitors Artificial Analysis leaderboards via official API."""

import os
from datetime import datetime
from typing import List, Optional, Dict
import requests

from .base import BaseWatcher, WatchEvent


class LeaderboardWatcher(BaseWatcher):
    """
    Watcher for Artificial Analysis image generation leaderboards.
    
    Uses the official Artificial Analysis API:
    - https://artificialanalysis.ai/documentation
    - Rate limit: 1,000 requests/day (sufficient for hourly checks)
    - Only monitors models within MAX_RANK (default: 30)
    """

    API_BASE = "https://artificialanalysis.ai/api/v2/data/media"
    
    # 기본 최대 순위 (config에서 override 가능)
    DEFAULT_MAX_RANK = 30
    
    ENDPOINTS = {
        # Image
        'text-to-image': '/text-to-image',
        'image-editing': '/image-editing',
        # Video
        'text-to-video': '/text-to-video',
        'image-to-video': '/image-to-video',
        # Speech
        'text-to-speech': '/text-to-speech',
    }

    def __init__(self, leaderboard_config: dict, api_key: Optional[str] = None):
        """
        Initialize leaderboard watcher.
        
        Args:
            leaderboard_config: Configuration with 'name', 'leaderboards' list, and 'max_rank'
            api_key: Artificial Analysis API key
        """
        super().__init__(leaderboard_config)
        self.api_key = api_key or os.environ.get('ARTIFICIAL_ANALYSIS_API_KEY', '')
        self.leaderboards_to_watch = leaderboard_config.get('leaderboards', list(self.ENDPOINTS.keys()))
        # config에서 max_rank 읽기 (기본값: 30)
        self.max_rank = leaderboard_config.get('max_rank', self.DEFAULT_MAX_RANK)

    @property
    def source_name(self) -> str:
        return 'leaderboard'

    def _get_headers(self) -> dict:
        """Build request headers with API key."""
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'AI-Model-Release-Watcher/1.0',
        }
        if self.api_key:
            headers['x-api-key'] = self.api_key
        return headers

    def check_updates(self, last_check_state: Optional[dict]) -> tuple[List[WatchEvent], dict]:
        """Check for leaderboard changes via API."""
        import time
        
        events = []
        new_state = last_check_state.copy() if last_check_state else {}

        if not self.api_key:
            print("[LeaderboardWatcher] Warning: No API key configured. Set ARTIFICIAL_ANALYSIS_API_KEY in .env")
            return [], new_state

        for i, board_name in enumerate(self.leaderboards_to_watch):
            if board_name not in self.ENDPOINTS:
                continue
            
            # Respectful delay between requests
            if i > 0:
                time.sleep(1)
            
            endpoint = self.ENDPOINTS[board_name]
            board_events, new_state = self._check_leaderboard_api(board_name, endpoint, new_state)
            events.extend(board_events)

        return events, new_state

    def _check_leaderboard_api(self, board_name: str, endpoint: str, state: dict) -> tuple[List[WatchEvent], dict]:
        """Check a single leaderboard via API."""
        events = []
        state_key = f"leaderboard_{board_name}"
        
        try:
            url = f"{self.API_BASE}{endpoint}"
            response = requests.get(url, headers=self._get_headers(), timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                models_data = data.get('data', [])
                
                if models_data:
                    # Build current rankings (30등 이내만 추적)
                    current_rankings = {}
                    current_models = []
                    
                    for model in models_data:
                        model_name = model.get('name', 'Unknown')
                        rank = model.get('rank', 0)
                        elo = model.get('elo', 0)
                        
                        # max_rank 이내의 모델만 추적
                        if rank > self.max_rank:
                            continue
                        
                        current_rankings[model_name] = {
                            'rank': rank,
                            'elo': elo,
                            'id': model.get('id'),
                            'creator': model.get('model_creator', {}).get('name', 'Unknown'),
                        }
                        current_models.append(model_name)
                    
                    # Get previous state
                    previous_data = state.get(state_key, {})
                    previous_rankings = previous_data.get('rankings', {})
                    previous_models = set(previous_data.get('models', []))
                    
                    current_models_set = set(current_models)
                    
                    # Detect new models
                    new_models = current_models_set - previous_models
                    for model_name in new_models:
                        model_info = current_rankings.get(model_name, {})
                        events.append(WatchEvent(
                            source='leaderboard',
                            event_type='leaderboard_new_entry',
                            model_name=model_name,
                            title=f"New model on {board_name}: {model_name}",
                            description=f"Rank: #{model_info.get('rank', 'N/A')} | ELO: {model_info.get('elo', 'N/A')} | Creator: {model_info.get('creator', 'Unknown')}",
                            url=f"https://artificialanalysis.ai/image/leaderboard/{board_name}",
                            timestamp=datetime.utcnow(),
                            extra_data={
                                'leaderboard': board_name,
                                'rank': model_info.get('rank'),
                                'elo': model_info.get('elo'),
                                'creator': model_info.get('creator'),
                                'action': 'new_entry',
                            }
                        ))
                    
                    # Detect ranking changes for existing models
                    if previous_rankings:
                        for model_name, current_info in current_rankings.items():
                            if model_name in previous_rankings:
                                prev_rank = previous_rankings[model_name].get('rank', 0)
                                curr_rank = current_info.get('rank', 0)
                                prev_elo = previous_rankings[model_name].get('elo', 0)
                                curr_elo = current_info.get('elo', 0)
                                
                                if curr_rank != prev_rank:
                                    direction = "up" if curr_rank < prev_rank else "down"
                                    change = abs(prev_rank - curr_rank)
                                    elo_change = curr_elo - prev_elo
                                    
                                    events.append(WatchEvent(
                                        source='leaderboard',
                                        event_type='leaderboard_rank_change',
                                        model_name=model_name,
                                        title=f"{model_name} moved {direction} on {board_name}",
                                        description=f"Rank: #{prev_rank} → #{curr_rank} ({'+' if direction == 'up' else ''}{-change if direction == 'up' else change}) | ELO: {prev_elo} → {curr_elo} ({'+' if elo_change >= 0 else ''}{elo_change:.0f})",
                                        url=f"https://artificialanalysis.ai/image/leaderboard/{board_name}",
                                        timestamp=datetime.utcnow(),
                                        extra_data={
                                            'leaderboard': board_name,
                                            'previous_rank': prev_rank,
                                            'current_rank': curr_rank,
                                            'previous_elo': prev_elo,
                                            'current_elo': curr_elo,
                                            'direction': direction,
                                            'change': change,
                                        }
                                    ))
                    
                    # Detect top 3 changes
                    current_top3 = [m for m in current_models if current_rankings.get(m, {}).get('rank', 99) <= 3]
                    current_top3.sort(key=lambda m: current_rankings.get(m, {}).get('rank', 99))
                    
                    previous_top3 = previous_data.get('top3', [])
                    
                    if previous_top3 and current_top3 != previous_top3:
                        top3_info = ", ".join([
                            f"#{current_rankings[m]['rank']} {m}" for m in current_top3[:3]
                        ])
                        events.append(WatchEvent(
                            source='leaderboard',
                            event_type='leaderboard_top3_change',
                            model_name='Top 3',
                            title=f"Top 3 changed on {board_name} leaderboard",
                            description=f"New Top 3: {top3_info}",
                            url=f"https://artificialanalysis.ai/image/leaderboard/{board_name}",
                            timestamp=datetime.utcnow(),
                            extra_data={
                                'leaderboard': board_name,
                                'previous_top3': previous_top3,
                                'current_top3': current_top3[:3],
                            }
                        ))
                    
                    # Update state
                    state[state_key] = {
                        'rankings': current_rankings,
                        'models': current_models,
                        'top3': current_top3[:3],
                        'last_checked': datetime.utcnow().isoformat(),
                        'total_models': len(current_models),
                    }
                    
            elif response.status_code == 401:
                print(f"[LeaderboardWatcher] API key invalid or missing for {board_name}")
            elif response.status_code == 429:
                print(f"[LeaderboardWatcher] Rate limit exceeded for {board_name}")
            else:
                print(f"[LeaderboardWatcher] API error {response.status_code} for {board_name}")
                    
        except requests.RequestException as e:
            print(f"[LeaderboardWatcher] Error fetching {board_name}: {e}")
        except Exception as e:
            print(f"[LeaderboardWatcher] Error processing {board_name}: {e}")

        return events, state
