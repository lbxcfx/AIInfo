from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.item import Item
from app.models.source import Source


INDEX_UID = "items"


def _headers() -> dict[str, str]:
    settings = get_settings()
    headers = {"Content-Type": "application/json"}
    if settings.meilisearch_master_key:
        headers["Authorization"] = f"Bearer {settings.meilisearch_master_key}"
    return headers


def _base_url() -> str:
    return get_settings().meilisearch_url.rstrip("/")


def _published_ts(value: datetime | None) -> int:
    if value is None:
        return 0
    return int(value.timestamp())


def item_document(item: Item, source: Source) -> dict[str, Any]:
    return {
        "id": item.id,
        "source_id": item.source_id,
        "source_name": source.name,
        "source_tier": source.tier,
        "source_type": source.source_type,
        "canonical_url": item.canonical_url,
        "title_original": item.title_original,
        "title_zh": item.title_zh,
        "summary_short": item.summary_short,
        "category": item.category,
        "language": item.language,
        "entities": item.entities,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "published_ts": _published_ts(item.published_at),
        "is_ai_related": item.is_ai_related,
        "is_featured": item.is_featured,
        "relevance_score": item.relevance_score,
        "final_score": item.final_score,
    }


async def ensure_search_index() -> None:
    settings_payload = {
        "searchableAttributes": [
            "title_zh",
            "title_original",
            "summary_short",
            "source_name",
            "category",
        ],
        "filterableAttributes": [
            "category",
            "source_id",
            "source_tier",
            "is_featured",
            "is_ai_related",
        ],
        "sortableAttributes": ["final_score", "published_ts", "relevance_score"],
        "displayedAttributes": ["*"],
    }
    async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
        index_response = await client.get(f"{_base_url()}/indexes/{INDEX_UID}", headers=_headers())
        if index_response.status_code == 404:
            create_response = await client.post(
                f"{_base_url()}/indexes",
                headers=_headers(),
                json={"uid": INDEX_UID, "primaryKey": "id"},
            )
            create_response.raise_for_status()
        else:
            index_response.raise_for_status()
        response = await client.patch(
            f"{_base_url()}/indexes/{INDEX_UID}/settings",
            headers=_headers(),
            json=settings_payload,
        )
        response.raise_for_status()


async def reindex_items(db: AsyncSession, limit: int = 2000) -> dict[str, Any]:
    await ensure_search_index()
    stmt = (
        select(Item, Source)
        .join(Source, Source.id == Item.source_id)
        .where(Item.is_ai_related.is_(True))
        .order_by(desc(Item.final_score), desc(Item.published_at).nullslast())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    documents = [item_document(item, source) for item, source in rows]
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        await client.delete(f"{_base_url()}/indexes/{INDEX_UID}/documents", headers=_headers())
        if documents:
            response = await client.post(
                f"{_base_url()}/indexes/{INDEX_UID}/documents",
                headers=_headers(),
                json=documents,
            )
            response.raise_for_status()
            task = response.json()
        else:
            task = None
    return {"indexed": len(documents), "task": task}


async def search_index(
    query: str,
    *,
    limit: int = 30,
    category: str | None = None,
    featured_only: bool = False,
) -> list[str]:
    await ensure_search_index()
    filters = ["is_ai_related = true"]
    if featured_only:
        filters.append("is_featured = true")
    if category:
        escaped = category.replace('"', '\\"')
        filters.append(f'category = "{escaped}"')
    payload: dict[str, Any] = {
        "q": query,
        "limit": limit,
        "filter": " AND ".join(filters),
        "sort": ["final_score:desc", "published_ts:desc"],
    }
    async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
        response = await client.post(
            f"{_base_url()}/indexes/{INDEX_UID}/search",
            headers=_headers(),
            json=payload,
        )
        response.raise_for_status()
        hits = response.json().get("hits", [])
    return [hit["id"] for hit in hits if hit.get("id")]


async def fallback_db_search(
    db: AsyncSession,
    query: str,
    *,
    limit: int = 30,
    category: str | None = None,
    featured_only: bool = False,
) -> list[tuple[Item, Source]]:
    pattern = f"%{query.strip()}%"
    stmt = (
        select(Item, Source)
        .join(Source, Source.id == Item.source_id)
        .where(
            Item.is_ai_related.is_(True),
            or_(
                Item.title_original.ilike(pattern),
                Item.summary_short.ilike(pattern),
                Source.name.ilike(pattern),
            ),
        )
        .order_by(desc(Item.final_score), desc(Item.published_at).nullslast())
        .limit(limit)
    )
    if category:
        stmt = stmt.where(Item.category == category)
    if featured_only:
        stmt = stmt.where(Item.is_featured.is_(True))
    return list((await db.execute(stmt)).all())
