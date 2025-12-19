#!/usr/bin/env python3
"""
AI Model Release Watcher
========================
Monitors various sources for AI model releases and sends notifications via Slack.

Supported sources:
- GitHub (repositories, commits, releases)
- Hugging Face Hub (models, updates)
- ModelScope (models, updates)
- arXiv (papers)
- Google News (articles)
- Artificial Analysis Leaderboards (rankings)

Features:
- Multi-channel Slack notifications
- Announcement vs Launch detection
- Leaderboard change tracking
- 24/7 Docker deployment

Usage:
    python main.py              # Run once
    python main.py --daemon     # Run as scheduled daemon
    python main.py --test       # Test Slack connection
"""

import argparse
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from models.state import StateManager
from notifiers.slack import SlackNotifier
from utils.config_loader import load_config, Config, ModelConfig
from watchers.base import WatchEvent, ReleaseStage
from watchers.github_watcher import GitHubWatcher
from watchers.huggingface_watcher import HuggingFaceWatcher
from watchers.modelscope_watcher import ModelScopeWatcher
from watchers.arxiv_watcher import ArxivWatcher
from watchers.news_watcher import NewsWatcher
from watchers.leaderboard_watcher import LeaderboardWatcher


class WatcherService:
    """Main service that orchestrates all watchers."""

    def __init__(self, config: Config):
        self.config = config
        
        # Ensure data directory exists
        db_path = Path(config.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.state_manager = StateManager(config.database_path)
        self.notifier = SlackNotifier(
            webhook_url=config.slack_webhook_url,
            include_icons=config.notifications.include_icons,
            include_timestamp=config.notifications.include_timestamp,
            mention_channel_for=config.notifications.mention_channel_for,
            channel_webhooks=config.slack_channels,
        )
        self.watchers = []
        self._setup_watchers()

    def _setup_watchers(self):
        """Set up watchers for all configured models and leaderboards."""
        # Model watchers
        for model_config in self.config.models:
            model_dict = {
                'name': model_config.name,
                'github': model_config.github,
                'huggingface': model_config.huggingface,
                'modelscope': model_config.modelscope,
                'arxiv_query': model_config.arxiv_query,
                'news_keywords': model_config.news_keywords,
            }

            # Add watchers for each configured source
            if model_config.github:
                self.watchers.append(
                    GitHubWatcher(model_dict, self.config.github_token)
                )
            
            if model_config.huggingface:
                self.watchers.append(
                    HuggingFaceWatcher(model_dict, self.config.huggingface_token)
                )
            
            if model_config.modelscope:
                self.watchers.append(
                    ModelScopeWatcher(model_dict)
                )
            
            if model_config.arxiv_query:
                self.watchers.append(
                    ArxivWatcher(model_dict)
                )
            
            if model_config.news_keywords:
                self.watchers.append(
                    NewsWatcher(model_dict)
                )

        # Leaderboard watcher
        if self.config.leaderboards.enabled:
            leaderboard_config = {
                'name': 'AI Image Generation',
                'leaderboards': self.config.leaderboards.boards,
                'max_rank': self.config.leaderboards.max_rank,
            }
            self.watchers.append(LeaderboardWatcher(
                leaderboard_config, 
                api_key=self.config.artificial_analysis_api_key
            ))

        print(f"[WatcherService] Initialized {len(self.watchers)} watchers")
        print(f"  - Models: {len(self.config.models)}")
        print(f"  - Priority models: {list(self.config.get_priority_model_names())}")
        print(f"  - Leaderboards: {'enabled' if self.config.leaderboards.enabled else 'disabled'}")

    def check_all(self) -> List[WatchEvent]:
        """Run all watchers and collect events."""
        all_events = []
        
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running check...")
        
        for watcher in self.watchers:
            try:
                state_key = watcher.get_state_key()
                last_state = self.state_manager.get_state(state_key)
                
                # 첫 실행 여부 확인 (DB에 저장된 상태가 없으면 첫 실행)
                is_first_run = last_state is None
                
                events, new_state = watcher.check_updates(last_state)
                
                if is_first_run:
                    # 첫 실행 시에는 상태만 저장하고 알림은 보내지 않음
                    print(f"  [{watcher.source_name}:{watcher.model_name}] First run - initializing state (no notifications)")
                    if events:
                        print(f"    Skipped {len(events)} event(s) on first run")
                elif events:
                    print(f"  [{watcher.source_name}:{watcher.model_name}] Found {len(events)} new event(s)")
                    for event in events:
                        stage_info = f" [{event.release_stage.value}]" if event.release_stage != ReleaseStage.UNKNOWN else ""
                        print(f"    - {event.event_type}: {event.title[:50]}...{stage_info}")
                    all_events.extend(events)
                
                # Save the new state
                self.state_manager.save_state(state_key, new_state)
                
            except Exception as e:
                print(f"  [{watcher.source_name}:{watcher.model_name}] Error: {e}")
        
        return all_events

    def _is_priority_event(self, event: WatchEvent) -> bool:
        """Check if an event is from a priority model."""
        return self.config.is_priority_model(event.model_name)

    def _mark_priority_events(self, events: List[WatchEvent]) -> List[WatchEvent]:
        """Mark priority model events for special handling."""
        priority_names = self.config.get_priority_model_names()
        
        for event in events:
            if event.model_name.lower() in priority_names:
                # Mark as priority in extra_data
                if event.extra_data is None:
                    event.extra_data = {}
                event.extra_data['is_priority'] = True
                event.extra_data['priority_model'] = True
        
        return events

    def run_once(self):
        """Run a single check and send notifications."""
        events = self.check_all()
        
        if events:
            print(f"\n[WatcherService] Sending {len(events)} notification(s)...")
            
            # Mark priority events
            events = self._mark_priority_events(events)
            
            # Separate priority model events (like Z-Image)
            priority_events = [e for e in events if self._is_priority_event(e)]
            normal_events = [e for e in events if not self._is_priority_event(e)]
            
            # Group normal events for routing
            announcements = [e for e in normal_events if e.release_stage == ReleaseStage.ANNOUNCED]
            launches = [e for e in normal_events if e.release_stage == ReleaseStage.LAUNCHED]
            leaderboard_events = [e for e in normal_events if e.source == 'leaderboard']
            other_events = [e for e in normal_events if e not in announcements + launches + leaderboard_events]
            
            sent = 0
            
            # Priority model events - send to main channel with @channel mention
            if priority_events:
                print(f"  - Priority models (Z-Image etc.): {len(priority_events)} event(s)")
                for event in priority_events:
                    # Add @channel mention for priority events
                    priority_config = self.config.get_priority_config(event.model_name)
                    if priority_config and priority_config.mention_channel:
                        # Temporarily add event type to mention list
                        original_mention_list = self.notifier.mention_channel_for.copy()
                        if event.event_type not in self.notifier.mention_channel_for:
                            self.notifier.mention_channel_for.append(event.event_type)
                        
                        if self.notifier.send_event(event):
                            sent += 1
                            print(f"    ★ [{event.source}] {event.title[:50]}...")
                        
                        # Restore original mention list
                        self.notifier.mention_channel_for = original_mention_list
                    else:
                        if self.notifier.send_event(event):
                            sent += 1
                            print(f"    ★ [{event.source}] {event.title[:50]}...")
            
            # Send leaderboard events combined as a single message
            if leaderboard_events:
                if self.notifier.send_leaderboard_combined(leaderboard_events):
                    sent += 1
                    print(f"  - Leaderboard: {len(leaderboard_events)} event(s) combined into 1 message")
            
            # Send announcements to announcements channel
            if announcements:
                sent += self.notifier.send_to_channel('announcements', announcements)
                print(f"  - Announcements: {len(announcements)} event(s)")
            
            # Send launches to launches channel
            if launches:
                sent += self.notifier.send_to_channel('launches', launches)
                print(f"  - Launches: {len(launches)} event(s)")
            
            # Send other events to default channel
            if other_events:
                sent += self.notifier.send_events(other_events)
                print(f"  - Other: {len(other_events)} event(s)")
            
            print(f"[WatcherService] Successfully sent {sent}/{len(events)} notifications")
        else:
            print("[WatcherService] No new events found")
        
        return events

    def run_daemon(self):
        """Run as a scheduled daemon."""
        scheduler = BlockingScheduler()
        
        # Add the job
        scheduler.add_job(
            self.run_once,
            trigger=IntervalTrigger(hours=self.config.check_interval_hours),
            id='watcher_job',
            name='AI Model Watcher',
            next_run_time=datetime.now(),  # Run immediately on start
        )
        
        print(f"\n[WatcherService] Starting daemon (interval: {self.config.check_interval_hours}h)")
        print("[WatcherService] Press Ctrl+C to stop\n")
        
        # Handle graceful shutdown
        def shutdown(signum, frame):
            print("\n[WatcherService] Shutting down...")
            scheduler.shutdown(wait=False)
            sys.exit(0)
        
        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)
        
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            pass

    def test_notification(self):
        """Test the Slack webhook connections."""
        print("[WatcherService] Testing Slack connections...")
        
        success = True
        
        # Test main webhook
        print("  - Main channel: ", end="")
        if self.notifier.test_connection():
            print("OK")
        else:
            print("FAILED")
            success = False
        
        # Test additional channels
        for channel_name, webhook_url in self.config.slack_channels.items():
            if webhook_url and not webhook_url.startswith('https://hooks.slack.com/services/YOUR'):
                print(f"  - {channel_name} channel: ", end="")
                if self.notifier.test_connection(webhook_url):
                    print("OK")
                else:
                    print("FAILED")
                    success = False
        
        if success:
            print("[WatcherService] All Slack connections successful!")
        else:
            print("[WatcherService] Some Slack connections failed. Check your webhook URLs.")
        
        return success


def main():
    parser = argparse.ArgumentParser(
        description='AI Model Release Watcher',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py              # Run check once
    python main.py --daemon     # Run continuously (hourly)
    python main.py --test       # Test Slack connection
    python main.py --config custom.yaml  # Use custom config file

Docker:
    docker-compose up -d        # Start 24/7 monitoring
    docker-compose logs -f      # View logs
    docker-compose down         # Stop monitoring
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Path to configuration file (default: config.yaml)'
    )
    
    parser.add_argument(
        '--daemon', '-d',
        action='store_true',
        help='Run as daemon with scheduled checks'
    )
    
    parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='Test Slack webhook connection'
    )
    
    parser.add_argument(
        '--clear-state',
        action='store_true',
        help='Clear all saved states (will re-detect everything)'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = load_config(args.config)
        print(f"[Main] Loaded configuration from {args.config}")
    except FileNotFoundError:
        print(f"[Main] Error: Configuration file not found: {args.config}")
        print("[Main] Please create a config.yaml file. See config.yaml for reference.")
        sys.exit(1)
    except Exception as e:
        print(f"[Main] Error loading configuration: {e}")
        sys.exit(1)
    
    # Initialize service
    service = WatcherService(config)
    
    # Handle clear state
    if args.clear_state:
        print("[Main] Clearing all saved states...")
        service.state_manager.clear_all_states()
        print("[Main] States cleared.")
        return
    
    # Handle test mode
    if args.test:
        success = service.test_notification()
        sys.exit(0 if success else 1)
    
    # Run
    if args.daemon:
        service.run_daemon()
    else:
        service.run_once()


if __name__ == '__main__':
    main()
