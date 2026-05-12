from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.items import to_item_read
from app.db.session import get_db
from app.models.item import Item
from app.models.source import Source
from app.schemas.common import ApiResponse
from app.schemas.item import ItemRead
from app.services.search import fallback_db_search, search_index


router = APIRouter(tags=["search"])


@router.get("/search")
async def search_items(
    q: str = Query(default="", max_length=160),
    limit: int = Query(default=30, ge=1, le=100),
    category: str | None = None,
    featured_only: bool = False,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[ItemRead]]:
    query = q.strip()
    if not query:
        rows = await fallback_db_search(
            db,
            "AI",
            limit=limit,
            category=category,
            featured_only=featured_only,
        )
        return ApiResponse(data=[to_item_read(item, source) for item, source in rows])

    try:
        ids = await search_index(
            query,
            limit=limit,
            category=category,
            featured_only=featured_only,
        )
    except Exception:
        rows = await fallback_db_search(
            db,
            query,
            limit=limit,
            category=category,
            featured_only=featured_only,
        )
        return ApiResponse(data=[to_item_read(item, source) for item, source in rows])

    if not ids:
        rows = await fallback_db_search(
            db,
            query,
            limit=limit,
            category=category,
            featured_only=featured_only,
        )
        return ApiResponse(data=[to_item_read(item, source) for item, source in rows])

    stmt = select(Item, Source).join(Source, Source.id == Item.source_id).where(Item.id.in_(ids))
    rows = (await db.execute(stmt)).all()
    by_id = {item.id: (item, source) for item, source in rows}
    ordered = [by_id[item_id] for item_id in ids if item_id in by_id]
    return ApiResponse(data=[to_item_read(item, source) for item, source in ordered])
