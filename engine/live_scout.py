"""Live intelligence scout discovering verified 24h developments per category without static RSS."""

import logging
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict

logger = logging.getLogger(__name__)

def scout_category_intel(category_key: str, queries: List[str], max_items: int = 15) -> List[Dict[str, str]]:
    """Scouts verified real-time developments from the past 24 hours for a specific category."""
    articles = []
    seen_titles = set()

    for query in queries:
        encoded_q = urllib.parse.quote(query)
        feed_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=en-US&gl=US&ceid=US:en"

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
            logger.warning(f"[LiveScout] Notice scouting '{query[:35]}...': {e}")

    logger.info(f"[LiveScout] Scouted {len(articles)} verified real-time items for category '{category_key}'.")
    return articles

def format_category_dossier(articles: List[Dict[str, str]], exclusions: List[str]) -> str:
    """Formats raw intelligence and injects category-specific exclusion mandates."""
    sections = []

    if exclusions:
        sections.append("CRITICAL EXCLUSION MANDATE (ALREADY PUBLISHED STORIES):")
        sections.append("You are strictly forbidden from selecting, summarizing, or covering any topic listed below:")
        for excl in exclusions:
            sections.append(f"  • [DO NOT COVER] {excl}")
        sections.append("")

    sections.append("VERIFIED REAL-TIME 24-HOUR INTELLIGENCE CANDIDATES:")
    if not articles:
        sections.append("No candidates retrieved from live scout. Identify the single most significant breaking 24h event in this category.")
    else:
        for idx, art in enumerate(articles, 1):
            sections.append(f"[{idx}] {art['title']}")
            if art.get("published"):
                sections.append(f"    Published: {art['published']}")
            if art.get("link"):
                sections.append(f"    Source Link: {art['link']}")
            sections.append("")

    return "\n".join(sections)
