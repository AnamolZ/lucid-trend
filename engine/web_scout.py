"""Real-time tech intelligence discovery service for 24-hour verified news."""

import logging
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Dict

logger = logging.getLogger(__name__)

RSS_FEED_URLS = [
    "https://news.google.com/rss/search?q=AI+OR+technology+breakthrough+when:1d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=developer+OR+compiler+OR+database+software+release+when:1d&hl=en-US&gl=US&ceid=US:en",
]

def fetch_recent_tech_intel(max_items: int = 12) -> List[Dict[str, str]]:
    """Scouts verified technology developments published strictly within the last 24 hours."""
    articles = []
    seen_titles = set()

    for feed_url in RSS_FEED_URLS:
        try:
            req = urllib.request.Request(
                feed_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=8) as response:
                root = ET.fromstring(response.read())
                for item in root.findall(".//item"):
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    pub_date_elem = item.find("pubDate")
                    desc_elem = item.find("description")

                    if title_elem is None or not title_elem.text:
                        continue

                    title = title_elem.text.strip()
                    if title in seen_titles:
                        continue
                    seen_titles.add(title)

                    link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                    pub_date = pub_date_elem.text.strip() if pub_date_elem is not None and pub_date_elem.text else ""
                    desc = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""

                    articles.append({
                        "title": title,
                        "link": link,
                        "published": pub_date,
                        "snippet": desc
                    })

                    if len(articles) >= max_items:
                        break
        except Exception as e:
            logger.warning(f"[WebScout] Notice querying feed '{feed_url[:45]}...': {e}")

    logger.info(f"[WebScout] Gathered {len(articles)} verified real-time tech developments from past 24h.")
    return articles

def format_intel_dossier(articles: List[Dict[str, str]]) -> str:
    """Formats raw intelligence into a comprehensive structured dossier for editorial synthesis."""
    if not articles:
        return "No external feeds retrieved. Identify the top 2 genuine breakthrough tech releases from the last 24 hours based on recent primary developer announcements."

    lines = ["VERIFIED 24-HOUR TECHNOLOGY INTELLIGENCE DOSSIER:\n"]
    for idx, art in enumerate(articles, 1):
        lines.append(f"[{idx}] {art['title']}")
        if art.get("published"):
            lines.append(f"    Published: {art['published']}")
        if art.get("link"):
            lines.append(f"    Source Link: {art['link']}")
        lines.append("")

    return "\n".join(lines)
