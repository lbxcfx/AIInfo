from collections import defaultdict
from datetime import UTC, date, datetime, time
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.items import to_item_read
from app.db.session import get_db
from app.models.item import Item
from app.models.source import Source
from app.schemas.common import ApiResponse


router = APIRouter(tags=["daily"])


@router.get("/daily")
async def daily_digest(
    day: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    target_day = day or datetime.now(UTC).date()
    start_at = datetime.combine(target_day, time.min, tzinfo=UTC)
    end_at = datetime.combine(target_day, time.max, tzinfo=UTC)
    stmt = (
        select(Item, Source)
        .join(Source, Source.id == Item.source_id)
        .where(
            Item.is_ai_related.is_(True),
            Item.is_featured.is_(True),
            Item.published_at >= start_at,
            Item.published_at <= end_at,
        )
        .order_by(desc(Item.final_score), desc(Item.published_at).nullslast())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    mode = "date"
    if not rows:
        mode = "latest_fallback"
        stmt = (
            select(Item, Source)
            .join(Source, Source.id == Item.source_id)
            .where(Item.is_ai_related.is_(True), Item.is_featured.is_(True))
            .order_by(desc(Item.final_score), desc(Item.published_at).nullslast())
            .limit(limit)
        )
        rows = (await db.execute(stmt)).all()

    groups: dict[str, list] = defaultdict(list)
    for item, source in rows:
        groups[item.category].append(to_item_read(item, source).model_dump(mode="json"))

    return ApiResponse(
        data={
            "date": target_day.isoformat(),
            "mode": mode,
            "generated_at": datetime.now(UTC).isoformat(),
            "total": len(rows),
            "groups": [
                {"category": category, "items": items}
                for category, items in sorted(groups.items(), key=lambda entry: len(entry[1]), reverse=True)
            ],
        }
    )
