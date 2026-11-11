"""Live intelligence scout discovering verified 24h developments per category without static RSS."""

import logging
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict

from service.data_cleaning.gemini import are_articles_semantic_duplicates

logger = logging.getLogger(__name__)


def _filter_fresh_candidates(
    articles: List[Dict[str, str]], exclusions: List[str], min_fallback: int = 3
) -> List[Dict[str, str]]:
    """Filters out RSS candidates semantically matching recently published headlines."""
    if not articles or not exclusions:
        return articles

    exclusion_docs = [{"title": excl} for excl in exclusions if excl]
    fresh = [
        art for art in articles
        if not any(
            are_articles_semantic_duplicates(
                {"title": art.get("title", ""), "description": art.get("snippet", "")},
                excl_doc,
            )
            for excl_doc in exclusion_docs
        )
    ]
    if len(fresh) < min_fallback:
        logger.warning(
            f"[LiveScout] Only {len(fresh)} fresh candidates after exclusion filter; "
            f"keeping all {len(articles)} candidates so drafting is not starved."
        )
        return articles

    removed = len(articles) - len(fresh)
    if removed:
        logger.info(f"[LiveScout] Pre-filtered {removed} duplicate RSS candidates; {len(fresh)} fresh remain.")
    return fresh

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
    candidates = _filter_fresh_candidates(articles, exclusions)

    if exclusions:
        sections.append("CRITICAL EXCLUSION MANDATE (ALREADY PUBLISHED STORIES):")
        sections.append("You are strictly forbidden from selecting, summarizing, or covering any topic listed below:")
        for excl in exclusions:
            sections.append(f"  • [DO NOT COVER] {excl}")
        sections.append("")

    sections.append("VERIFIED REAL-TIME 24-HOUR INTELLIGENCE CANDIDATES:")
    if not candidates:
        sections.append("No candidates retrieved from live scout. Identify the single most significant breaking 24h event in this category.")
    else:
        for idx, art in enumerate(candidates, 1):
            sections.append(f"[{idx}] {art['title']}")
            if art.get("published"):
                sections.append(f"    Published: {art['published']}")
            if art.get("link"):
                sections.append(f"    Source Link: {art['link']}")
            sections.append("")

    return "\n".join(sections)
