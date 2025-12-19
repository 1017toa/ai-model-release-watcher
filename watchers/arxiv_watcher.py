"""arXiv Watcher - monitors arXiv for new papers related to models."""

from datetime import datetime
from typing import List, Optional
import hashlib
import requests
import xml.etree.ElementTree as ET

from .base import BaseWatcher, WatchEvent


class ArxivWatcher(BaseWatcher):
    """Watcher for arXiv paper publications."""

    API_BASE = "http://export.arxiv.org/api/query"

    def __init__(self, model_config: dict):
        super().__init__(model_config)
        self.search_query = model_config.get('arxiv_query')

    @property
    def source_name(self) -> str:
        return 'arxiv'

    def check_updates(self, last_check_state: Optional[dict]) -> tuple[List[WatchEvent], dict]:
        """Check for new papers on arXiv."""
        if not self.search_query:
            return [], last_check_state or {}

        events = []
        new_state = last_check_state.copy() if last_check_state else {}
        seen_ids = set(new_state.get('seen_paper_ids', []))

        try:
            # Build arXiv API query
            # Search in title and abstract
            query = f'all:"{self.search_query}"'
            params = {
                'search_query': query,
                'start': 0,
                'max_results': 10,
                'sortBy': 'submittedDate',
                'sortOrder': 'descending',
            }
            
            response = requests.get(self.API_BASE, params=params, timeout=30)
            
            if response.status_code == 200:
                papers = self._parse_arxiv_response(response.text)
                
                for paper in papers:
                    paper_id = paper['id']
                    
                    if paper_id not in seen_ids:
                        seen_ids.add(paper_id)
                        
                        events.append(WatchEvent(
                            source='arxiv',
                            event_type='new_paper',
                            model_name=self.model_name,
                            title=paper['title'],
                            description=paper['summary'][:400] + '...' if len(paper['summary']) > 400 else paper['summary'],
                            url=paper['url'],
                            timestamp=paper['published'],
                            extra_data={
                                'arxiv_id': paper['arxiv_id'],
                                'authors': paper['authors'][:5],
                                'categories': paper['categories'],
                            }
                        ))
                
                # Keep only the most recent 100 paper IDs
                new_state['seen_paper_ids'] = list(seen_ids)[-100:]
        except requests.RequestException:
            pass

        return events, new_state

    def _parse_arxiv_response(self, xml_content: str) -> List[dict]:
        """Parse arXiv API XML response."""
        papers = []
        
        try:
            # Define namespace
            ns = {
                'atom': 'http://www.w3.org/2005/Atom',
                'arxiv': 'http://arxiv.org/schemas/atom'
            }
            
            root = ET.fromstring(xml_content)
            
            for entry in root.findall('atom:entry', ns):
                # Get ID (extract arXiv ID from full URL)
                id_elem = entry.find('atom:id', ns)
                full_id = id_elem.text if id_elem is not None else ''
                arxiv_id = full_id.split('/abs/')[-1] if '/abs/' in full_id else full_id
                
                # Get title
                title_elem = entry.find('atom:title', ns)
                title = title_elem.text.strip().replace('\n', ' ') if title_elem is not None else 'No title'
                
                # Get summary/abstract
                summary_elem = entry.find('atom:summary', ns)
                summary = summary_elem.text.strip().replace('\n', ' ') if summary_elem is not None else ''
                
                # Get published date
                published_elem = entry.find('atom:published', ns)
                try:
                    published = datetime.fromisoformat(published_elem.text.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    published = datetime.utcnow()
                
                # Get authors
                authors = []
                for author in entry.findall('atom:author', ns):
                    name_elem = author.find('atom:name', ns)
                    if name_elem is not None:
                        authors.append(name_elem.text)
                
                # Get categories
                categories = []
                for category in entry.findall('atom:category', ns):
                    term = category.get('term')
                    if term:
                        categories.append(term)
                
                # Get URL
                url = f"https://arxiv.org/abs/{arxiv_id}"
                for link in entry.findall('atom:link', ns):
                    if link.get('type') == 'text/html':
                        url = link.get('href', url)
                        break
                
                papers.append({
                    'id': hashlib.md5(arxiv_id.encode()).hexdigest()[:16],
                    'arxiv_id': arxiv_id,
                    'title': title,
                    'summary': summary,
                    'published': published,
                    'authors': authors,
                    'categories': categories,
                    'url': url,
                })
        except ET.ParseError:
            pass

        return papers

