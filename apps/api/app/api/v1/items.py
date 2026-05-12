from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.item import Item
from app.models.source import Source
from app.schemas.common import ApiResponse
from app.schemas.item import ItemRead, SourceMini


router = APIRouter(tags=["items"])


def to_item_read(item: Item, source: Source) -> ItemRead:
    return ItemRead.model_validate(
        {
            **item.__dict__,
            "source": SourceMini.model_validate(source),
        }
    )


@router.get("/items")
async def list_items(
    limit: int = Query(default=30, ge=1, le=100),
    featured_only: bool = False,
    category: str | None = None,
    source_id: str | None = None,
    source_type: str | None = None,
    days: int | None = Query(default=None, ge=1, le=365),
    enhanced_only: bool = False,
    sort_by: str = Query(default="time", pattern="^(time|score)$"),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[ItemRead]]:
    order = (
        [desc(Item.final_score), desc(Item.published_at).nullslast()]
        if sort_by == "score"
        else [desc(Item.published_at).nullslast(), desc(Item.created_at)]
    )
    stmt = (
        select(Item, Source)
        .join(Source, Source.id == Item.source_id)
        .where(Item.is_ai_related.is_(True))
        .order_by(*order)
        .limit(limit)
    )
    if featured_only:
        stmt = stmt.where(Item.is_featured.is_(True))
    if category:
        stmt = stmt.where(Item.category == category)
    if source_id:
        stmt = stmt.where(Item.source_id == source_id)
    if source_type:
        stmt = stmt.where(Source.source_type == source_type)
    if days:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = stmt.where(Item.published_at >= since)
    if enhanced_only:
        stmt = stmt.where(Item.llm_processed_at.is_not(None))
    rows = (await db.execute(stmt)).all()
    return ApiResponse(data=[to_item_read(item, source) for item, source in rows])


@router.get("/featured")
async def list_featured(
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[ItemRead]]:
    stmt = (
        select(Item, Source)
        .join(Source, Source.id == Item.source_id)
        .where(Item.is_ai_related.is_(True), Item.is_featured.is_(True))
        .order_by(desc(Item.final_score), desc(Item.published_at).nullslast())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return ApiResponse(data=[to_item_read(item, source) for item, source in rows])
