"""GitHub Watcher - monitors GitHub repositories for new commits and releases."""

import re
from datetime import datetime
from typing import List, Optional
import requests

from .base import BaseWatcher, WatchEvent, ReleaseStage


class GitHubWatcher(BaseWatcher):
    """Watcher for GitHub repository updates."""

    API_BASE = "https://api.github.com"

    # Keywords indicating announcement (not yet released)
    ANNOUNCEMENT_KEYWORDS = [
        'coming soon', 'announcing', 'preview', 'teaser', 'upcoming',
        'will be released', 'stay tuned', 'sneak peek', 'roadmap',
        'planned', 'expected', 'eta', 'wip', 'work in progress',
        'alpha', 'beta', 'rc', 'release candidate', 'pre-release',
    ]

    # Keywords indicating actual release
    LAUNCH_KEYWORDS = [
        'released', 'available now', 'v1.', 'v2.', 'stable',
        'production ready', 'ready to use', 'download now',
        'install', 'pip install', 'weights released',
    ]

    def __init__(self, model_config: dict, github_token: Optional[str] = None):
        super().__init__(model_config)
        self.repo = model_config.get('github')
        self.token = github_token
        self._headers = self._build_headers()

    def _build_headers(self) -> dict:
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'AI-Model-Release-Watcher'
        }
        if self.token:
            headers['Authorization'] = f'token {self.token}'
        return headers

    @property
    def source_name(self) -> str:
        return 'github'

    def _detect_release_stage(self, text: str, is_prerelease: bool = False) -> ReleaseStage:
        """Detect whether text indicates announcement or actual launch."""
        if not text:
            return ReleaseStage.UNKNOWN
        
        text_lower = text.lower()
        
        # Check for prerelease flag first
        if is_prerelease:
            return ReleaseStage.ANNOUNCED
        
        # Check for announcement keywords
        for keyword in self.ANNOUNCEMENT_KEYWORDS:
            if keyword in text_lower:
                return ReleaseStage.ANNOUNCED
        
        # Check for launch keywords
        for keyword in self.LAUNCH_KEYWORDS:
            if keyword in text_lower:
                return ReleaseStage.LAUNCHED
        
        # Default based on context - if it's a release with assets, likely launched
        return ReleaseStage.UNKNOWN

    def check_updates(self, last_check_state: Optional[dict]) -> tuple[List[WatchEvent], dict]:
        """Check for new commits and releases on GitHub."""
        if not self.repo:
            return [], last_check_state or {}

        events = []
        new_state = last_check_state.copy() if last_check_state else {}

        # Check for new commits
        commit_events, new_state = self._check_commits(new_state)
        events.extend(commit_events)

        # Check for new releases
        release_events, new_state = self._check_releases(new_state)
        events.extend(release_events)

        # Check if repo exists (for new repo detection)
        repo_event, new_state = self._check_repo_exists(new_state)
        if repo_event:
            events.append(repo_event)

        return events, new_state

    def _check_repo_exists(self, state: dict) -> tuple[Optional[WatchEvent], dict]:
        """Check if the repository exists (for detecting new repos)."""
        if state.get('repo_known'):
            return None, state

        try:
            url = f"{self.API_BASE}/repos/{self.repo}"
            response = requests.get(url, headers=self._headers, timeout=30)
            
            if response.status_code == 200:
                repo_data = response.json()
                state['repo_known'] = True
                state['repo_created_at'] = repo_data.get('created_at')
                
                # Determine release stage from README/description
                description = repo_data.get('description', '')
                release_stage = self._detect_release_stage(description)
                
                # Check if there are actual releases
                has_releases = self._has_releases()
                if has_releases:
                    release_stage = ReleaseStage.LAUNCHED
                elif release_stage == ReleaseStage.UNKNOWN:
                    # New repo without releases is likely an announcement
                    release_stage = ReleaseStage.ANNOUNCED
                
                # If this is the first time we see this repo, report it
                created_at = datetime.fromisoformat(repo_data['created_at'].replace('Z', '+00:00'))
                
                event_type = 'release_launched' if release_stage == ReleaseStage.LAUNCHED else 'release_announced'
                
                return WatchEvent(
                    source='github',
                    event_type=event_type,
                    model_name=self.model_name,
                    title=f"Repository discovered: {self.repo}",
                    description=repo_data.get('description', 'No description'),
                    url=repo_data.get('html_url', f"https://github.com/{self.repo}"),
                    timestamp=created_at,
                    release_stage=release_stage,
                    extra_data={
                        'stars': repo_data.get('stargazers_count', 0),
                        'forks': repo_data.get('forks_count', 0),
                        'language': repo_data.get('language'),
                    }
                ), state
        except requests.RequestException:
            pass

        return None, state

    def _has_releases(self) -> bool:
        """Check if the repo has any releases."""
        try:
            url = f"{self.API_BASE}/repos/{self.repo}/releases"
            params = {'per_page': 1}
            response = requests.get(url, headers=self._headers, params=params, timeout=10)
            if response.status_code == 200:
                releases = response.json()
                return len(releases) > 0
        except requests.RequestException:
            pass
        return False

    def _check_commits(self, state: dict) -> tuple[List[WatchEvent], dict]:
        """Check for new commits."""
        events = []
        last_commit_sha = state.get('last_commit_sha')

        try:
            url = f"{self.API_BASE}/repos/{self.repo}/commits"
            params = {'per_page': 10}
            response = requests.get(url, headers=self._headers, params=params, timeout=30)
            
            if response.status_code == 200:
                commits = response.json()
                if commits:
                    latest_commit = commits[0]
                    latest_sha = latest_commit['sha']
                    
                    # If we have a last commit and it's different, report new commits
                    if last_commit_sha and latest_sha != last_commit_sha:
                        # Find new commits
                        new_commits = []
                        for commit in commits:
                            if commit['sha'] == last_commit_sha:
                                break
                            new_commits.append(commit)
                        
                        for commit in new_commits[:5]:  # Limit to 5 most recent
                            commit_data = commit.get('commit', {})
                            author = commit_data.get('author', {})
                            message = commit_data.get('message', 'No message')
                            
                            # Detect release stage from commit message
                            release_stage = self._detect_release_stage(message)
                            
                            events.append(WatchEvent(
                                source='github',
                                event_type='new_commit',
                                model_name=self.model_name,
                                title=message.split('\n')[0][:100],
                                description=f"Author: {author.get('name', 'Unknown')}",
                                url=commit.get('html_url', ''),
                                timestamp=datetime.fromisoformat(
                                    author.get('date', datetime.utcnow().isoformat()).replace('Z', '+00:00')
                                ),
                                release_stage=release_stage,
                                extra_data={
                                    'sha': commit['sha'][:7],
                                    'full_sha': commit['sha'],
                                }
                            ))
                    
                    state['last_commit_sha'] = latest_sha
        except requests.RequestException:
            pass

        return events, state

    def _check_releases(self, state: dict) -> tuple[List[WatchEvent], dict]:
        """Check for new releases."""
        events = []
        last_release_id = state.get('last_release_id')

        try:
            url = f"{self.API_BASE}/repos/{self.repo}/releases"
            params = {'per_page': 5}
            response = requests.get(url, headers=self._headers, params=params, timeout=30)
            
            if response.status_code == 200:
                releases = response.json()
                if releases:
                    latest_release = releases[0]
                    latest_id = latest_release['id']
                    
                    if last_release_id and latest_id != last_release_id:
                        # Report new releases
                        for release in releases:
                            if release['id'] == last_release_id:
                                break
                            
                            published_at = release.get('published_at') or release.get('created_at')
                            is_prerelease = release.get('prerelease', False)
                            
                            # Determine release stage
                            release_text = f"{release.get('name', '')} {release.get('body', '')}"
                            release_stage = self._detect_release_stage(release_text, is_prerelease)
                            
                            # If has assets and not prerelease, it's launched
                            if release.get('assets') and not is_prerelease:
                                release_stage = ReleaseStage.LAUNCHED
                            
                            event_type = 'release_launched' if release_stage == ReleaseStage.LAUNCHED else 'release_announced'
                            
                            events.append(WatchEvent(
                                source='github',
                                event_type=event_type,
                                model_name=self.model_name,
                                title=f"{'Release' if release_stage == ReleaseStage.LAUNCHED else 'Pre-release'}: {release.get('tag_name', 'Unknown')}",
                                description=release.get('name', '') or release.get('body', '')[:200],
                                url=release.get('html_url', ''),
                                timestamp=datetime.fromisoformat(
                                    published_at.replace('Z', '+00:00')
                                ),
                                release_stage=release_stage,
                                extra_data={
                                    'tag': release.get('tag_name'),
                                    'prerelease': is_prerelease,
                                    'has_assets': len(release.get('assets', [])) > 0,
                                }
                            ))
                    
                    state['last_release_id'] = latest_id
        except requests.RequestException:
            pass

        return events, state
