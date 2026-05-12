from datetime import datetime
from typing import Any

from app.schemas.common import OrmModel


class SourceMini(OrmModel):
    id: str
    name: str
    tier: str
    source_type: str


class ItemRead(OrmModel):
    id: str
    source_id: str
    canonical_url: str
    title_original: str
    title_zh: str | None = None
    summary_short: str
    language: str
    category: str
    entities: dict[str, Any]
    score_details: dict[str, Any] = {}
    published_at: datetime | None = None
    llm_processed_at: datetime | None = None
    is_ai_related: bool
    relevance_score: float
    final_score: float
    is_featured: bool
    processing_status: str
    source: SourceMini


class CrawlRunResult(OrmModel):
    sources_seen: int
    raw_created: int
    items_created: int
    errors: list[str]
