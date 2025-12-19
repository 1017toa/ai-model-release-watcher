"""News Watcher - monitors Google News RSS for articles about models."""

from datetime import datetime
from typing import List, Optional
from urllib.parse import quote
import hashlib
import requests

import feedparser

from .base import BaseWatcher, WatchEvent


class NewsWatcher(BaseWatcher):
    """Watcher for news articles via Google News RSS."""

    # Google News RSS URL template
    GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    def __init__(self, model_config: dict):
        super().__init__(model_config)
        self.keywords = model_config.get('news_keywords')

    @property
    def source_name(self) -> str:
        return 'news'

    def check_updates(self, last_check_state: Optional[dict]) -> tuple[List[WatchEvent], dict]:
        """Check for new news articles."""
        if not self.keywords:
            return [], last_check_state or {}

        events = []
        new_state = last_check_state.copy() if last_check_state else {}
        seen_ids = set(new_state.get('seen_article_ids', []))

        try:
            # Build Google News RSS URL
            query = quote(self.keywords)
            url = self.GOOGLE_NEWS_RSS.format(query=query)
            
            # Parse the RSS feed
            feed = feedparser.parse(url)
            
            if feed.entries:
                for entry in feed.entries[:15]:  # Limit to 15 most recent
                    # Create a unique ID from the link
                    article_id = hashlib.md5(entry.get('link', '').encode()).hexdigest()[:16]
                    
                    if article_id not in seen_ids:
                        seen_ids.add(article_id)
                        
                        # Parse published date
                        try:
                            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                                published = datetime(*entry.published_parsed[:6])
                            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                                published = datetime(*entry.updated_parsed[:6])
                            else:
                                published = datetime.utcnow()
                        except (TypeError, ValueError):
                            published = datetime.utcnow()
                        
                        # Get source name
                        source_name = 'Unknown Source'
                        if hasattr(entry, 'source') and entry.source:
                            source_name = entry.source.get('title', 'Unknown Source')
                        
                        # Clean up title (Google News adds source to title)
                        title = entry.get('title', 'No title')
                        if ' - ' in title:
                            title = title.rsplit(' - ', 1)[0]
                        
                        events.append(WatchEvent(
                            source='news',
                            event_type='new_article',
                            model_name=self.model_name,
                            title=title[:150],
                            description=f"Source: {source_name}",
                            url=entry.get('link', ''),
                            timestamp=published,
                            extra_data={
                                'source_name': source_name,
                            }
                        ))
                
                # Keep only the most recent 200 article IDs
                new_state['seen_article_ids'] = list(seen_ids)[-200:]
        except Exception as e:
            print(f"[NewsWatcher] Error fetching news: {e}")

        return events, new_state

