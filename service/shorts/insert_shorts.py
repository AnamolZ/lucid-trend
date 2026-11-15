from typing import List, Dict
from service.tursodb.client import TursoDBService


def insert_shorts(shorts_documents: List[Dict]) -> List[str]:
    """Helper to persist shorts documents into Turso DB."""
    turso = TursoDBService()
    return turso.insert_shorts(shorts_documents)


def get_recent_shorts(limit: int = 50) -> List[Dict]:
    """Helper to fetch recent shorts from Turso DB."""
    turso = TursoDBService()
    return turso.fetch_recent_shorts_for_export(limit=limit)
