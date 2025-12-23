"""Slack Notifier - sends notifications via Slack webhook."""

import json
from datetime import datetime
from typing import List, Optional, Dict
import requests

from watchers.base import WatchEvent


class SlackNotifier:
    """Sends notifications to Slack via webhook with multi-channel support."""

    # Source icons and colors
    SOURCE_CONFIG = {
        'github': {'icon': ':octocat:', 'color': '#24292e'},
        'huggingface': {'icon': ':hugging_face:', 'color': '#ffcc00'},
        'modelscope': {'icon': ':microscope:', 'color': '#1890ff'},
        'arxiv': {'icon': ':page_facing_up:', 'color': '#b31b1b'},
        'news': {'icon': ':newspaper:', 'color': '#4a90d9'},
        'leaderboard': {'icon': ':trophy:', 'color': '#ffd700'},
    }

    # Event type labels
    EVENT_LABELS = {
        'new_repo': 'New Repository',
        'new_commit': 'New Commit',
        'new_release': 'New Release',
        'new_model': 'New Model',
        'new_paper': 'New Paper',
        'new_article': 'News Article',
        'leaderboard_new_entry': 'Leaderboard: New Entry',
        'leaderboard_rank_change': 'Leaderboard: Rank Change',
        'leaderboard_top3_change': 'Leaderboard: Top 3 Change',
        'release_announced': 'Release Announced',
        'release_launched': 'Model Launched',
    }

    def __init__(
        self,
        webhook_url: str,
        include_icons: bool = True,
        include_timestamp: bool = True,
        mention_channel_for: Optional[List[str]] = None,
        channel_webhooks: Optional[Dict[str, str]] = None
    ):
        """
        Initialize the Slack notifier with multi-channel support.
        
        Args:
            webhook_url: Default Slack webhook URL
            include_icons: Whether to include source icons
            include_timestamp: Whether to include timestamps
            mention_channel_for: List of event types that should mention @channel
            channel_webhooks: Dict mapping channel names to webhook URLs for routing
        """
        self.webhook_url = webhook_url
        self.include_icons = include_icons
        self.include_timestamp = include_timestamp
        self.mention_channel_for = mention_channel_for or ['new_release', 'new_model', 'release_launched']
        self.channel_webhooks = channel_webhooks or {}

    def get_webhook_for_event(self, event: WatchEvent) -> str:
        """Get the appropriate webhook URL for an event."""
        # Route leaderboard events to leaderboard channel if configured
        if event.source == 'leaderboard' and 'leaderboard' in self.channel_webhooks:
            return self.channel_webhooks['leaderboard']
        
        # Route by event type
        if event.event_type in self.channel_webhooks:
            return self.channel_webhooks[event.event_type]
        
        # Route by source
        if event.source in self.channel_webhooks:
            return self.channel_webhooks[event.source]
        
        # Default webhook
        return self.webhook_url

    def send_event(self, event: WatchEvent, webhook_url: Optional[str] = None) -> bool:
        """
        Send a single event notification to Slack.
        
        Args:
            event: The event to notify about
            webhook_url: Optional override webhook URL
            
        Returns:
            True if successful, False otherwise
        """
        url = webhook_url or self.get_webhook_for_event(event)
        message = self._build_message(event)
        return self._send_webhook(message, url)

    def send_events(self, events: List[WatchEvent]) -> int:
        """
        Send multiple event notifications to Slack.
        
        Args:
            events: List of events to notify about
            
        Returns:
            Number of successfully sent notifications
        """
        success_count = 0
        for event in events:
            if self.send_event(event):
                success_count += 1
        return success_count

    def send_to_channel(self, channel_name: str, events: List[WatchEvent]) -> int:
        """
        Send events to a specific channel.
        
        Args:
            channel_name: Name of the channel (must be in channel_webhooks)
            events: List of events to send
            
        Returns:
            Number of successfully sent notifications
        """
        webhook_url = self.channel_webhooks.get(channel_name, self.webhook_url)
        success_count = 0
        for event in events:
            if self.send_event(event, webhook_url):
                success_count += 1
        return success_count

    def send_summary(self, events: List[WatchEvent], webhook_url: Optional[str] = None) -> bool:
        """
        Send a summary of multiple events as a single message.
        
        Args:
            events: List of events to summarize
            webhook_url: Optional override webhook URL
            
        Returns:
            True if successful, False otherwise
        """
        if not events:
            return True

        url = webhook_url or self.webhook_url
        message = self._build_summary_message(events)
        return self._send_webhook(message, url)

    def _build_message(self, event: WatchEvent) -> dict:
        """Build a Slack message payload for a single event."""
        source_config = self.SOURCE_CONFIG.get(event.source, {'icon': ':bell:', 'color': '#808080'})
        event_label = self.EVENT_LABELS.get(event.event_type, event.event_type)

        # Build header
        header = f"{event_label}: {event.model_name}"
        if self.include_icons:
            header = f"{source_config['icon']} {header}"

        # Check if we should mention channel
        text = ""
        if event.event_type in self.mention_channel_for:
            text = "<!channel> "

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": header[:150],  # Slack limit
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{event.title}*\n{event.description[:500]}"
                }
            }
        ]

        # Add extra data for leaderboard events
        if event.source == 'leaderboard' and event.extra_data:
            extra_text = []
            if event.extra_data.get('leaderboard'):
                extra_text.append(f"Leaderboard: {event.extra_data['leaderboard']}")
            if event.extra_data.get('current_rank'):
                extra_text.append(f"Current Rank: #{event.extra_data['current_rank']}")
            if event.extra_data.get('current_top3'):
                extra_text.append(f"Top 3: {', '.join(event.extra_data['current_top3'])}")
            
            if extra_text:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": " | ".join(extra_text)
                    }
                })

        # Add link button
        if event.url:
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Details",
                            "emoji": True
                        },
                        "url": event.url,
                        "action_id": "view_details"
                    }
                ]
            })

        # Add timestamp footer
        if self.include_timestamp:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Source: {event.source.upper()} | {event.timestamp.strftime('%Y-%m-%d %H:%M UTC')}"
                    }
                ]
            })

        return {
            "text": text + header,
            "attachments": [
                {
                    "color": source_config['color'],
                    "blocks": blocks
                }
            ]
        }

    def _build_summary_message(self, events: List[WatchEvent]) -> dict:
        """Build a summary message for multiple events."""
        # Group events by source
        by_source = {}
        for event in events:
            if event.source not in by_source:
                by_source[event.source] = []
            by_source[event.source].append(event)

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f":bell: AI Model Watcher Summary - {len(events)} Updates",
                    "emoji": True
                }
            }
        ]

        for source, source_events in by_source.items():
            source_config = self.SOURCE_CONFIG.get(source, {'icon': ':bell:'})
            
            event_list = "\n".join([
                f"• <{e.url}|{e.title[:50]}>" if e.url else f"• {e.title[:50]}"
                for e in source_events[:5]
            ])
            
            if len(source_events) > 5:
                event_list += f"\n_... and {len(source_events) - 5} more_"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{source_config['icon']} *{source.upper()}* ({len(source_events)})\n{event_list}"
                }
            })

        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Generated at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
                }
            ]
        })

        return {
            "text": f"AI Model Watcher: {len(events)} new updates",
            "blocks": blocks
        }

    def send_leaderboard_combined(self, events: List[WatchEvent], webhook_url: Optional[str] = None) -> bool:
        """
        Send multiple leaderboard events as a single combined message.
        
        Args:
            events: List of leaderboard events to combine
            webhook_url: Optional override webhook URL
            
        Returns:
            True if successful, False otherwise
        """
        if not events:
            return True

        url = webhook_url or self.channel_webhooks.get('leaderboard', self.webhook_url)
        message = self._build_leaderboard_combined_message(events)
        return self._send_webhook(message, url)

    def _build_leaderboard_combined_message(self, events: List[WatchEvent]) -> dict:
        """Build a combined message for multiple leaderboard events."""
        source_config = self.SOURCE_CONFIG.get('leaderboard', {'icon': ':trophy:', 'color': '#ffd700'})
        
        # Group events by leaderboard type
        by_leaderboard = {}
        for event in events:
            leaderboard = event.extra_data.get('leaderboard', 'Unknown') if event.extra_data else 'Unknown'
            if leaderboard not in by_leaderboard:
                by_leaderboard[leaderboard] = []
            by_leaderboard[leaderboard].append(event)

        # Build header
        total_changes = len(events)
        header = f"{source_config['icon']} Leaderboard Update - {total_changes} Changes"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": header[:150],
                    "emoji": True
                }
            }
        ]

        # Add events grouped by leaderboard
        for leaderboard, lb_events in by_leaderboard.items():
            # Build list of changes for this leaderboard
            changes_text = []
            for event in lb_events:
                extra = event.extra_data or {}
                model_name = event.model_name
                
                # Format rank change info
                if 'previous_rank' in extra and 'current_rank' in extra:
                    prev_rank = extra['previous_rank']
                    curr_rank = extra['current_rank']
                    rank_diff = prev_rank - curr_rank

                    if rank_diff > 0:
                        direction = f":arrow_up: +{rank_diff}"
                    elif rank_diff < 0:
                        direction = f":arrow_down: {rank_diff}"
                    else:
                        direction = "→"

                    rank_info = f"#{prev_rank} → #{curr_rank} ({direction})"
                elif 'rank' in extra:
                    # New entry - just show the rank
                    curr_rank = extra['rank']
                    rank_info = f"#{curr_rank}"
                else:
                    curr_rank = extra.get('current_rank', '?')
                    rank_info = f"#{curr_rank}"

                # Format ELO change if available
                elo_info = ""
                if 'previous_elo' in extra and 'current_elo' in extra:
                    prev_elo = extra['previous_elo']
                    curr_elo = extra['current_elo']
                    elo_diff = curr_elo - prev_elo
                    elo_sign = "+" if elo_diff >= 0 else ""
                    elo_info = f" | ELO: {prev_elo} → {curr_elo} ({elo_sign}{elo_diff})"

                changes_text.append(f"• {model_name}: {rank_info}{elo_info}")
            
            # Add section for this leaderboard
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{leaderboard}* ({len(lb_events)} changes)\n" + "\n".join(changes_text[:10])
                }
            })
            
            # Add "more" note if needed
            if len(lb_events) > 10:
                blocks.append({
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"_... and {len(lb_events) - 10} more changes_"
                        }
                    ]
                })

        # Add timestamp footer
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Source: LEADERBOARD | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
                }
            ]
        })

        return {
            "text": header,
            "attachments": [
                {
                    "color": source_config['color'],
                    "blocks": blocks
                }
            ]
        }

    def _send_webhook(self, message: dict, webhook_url: Optional[str] = None) -> bool:
        """Send a message to the Slack webhook."""
        url = webhook_url or self.webhook_url
        
        if not url or url.startswith('https://hooks.slack.com/services/YOUR'):
            print(f"[Slack] Webhook not configured. Message: {message.get('text', '')}")
            return False

        try:
            response = requests.post(
                url,
                json=message,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                return True
            else:
                print(f"[Slack] Failed to send: {response.status_code} - {response.text}")
                return False
        except requests.RequestException as e:
            print(f"[Slack] Error sending webhook: {e}")
            return False

    def test_connection(self, webhook_url: Optional[str] = None) -> bool:
        """Test the Slack webhook connection."""
        url = webhook_url or self.webhook_url
        test_message = {
            "text": ":white_check_mark: AI Model Watcher connected successfully!",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*AI Model Release Watcher* is now connected and monitoring for updates."
                    }
                }
            ]
        }
        return self._send_webhook(test_message, url)
