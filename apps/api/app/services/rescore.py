from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.text import heuristic_final_score
from app.models.item import Item
from app.models.raw_item import RawItem
from app.models.source import Source
from app.services.crawler import apply_source_specific_score


async def rescore_github_items(db: AsyncSession) -> dict[str, int]:
    rows = (
        await db.execute(
            select(Item, RawItem, Source)
            .join(RawItem, RawItem.id == Item.raw_id)
            .join(Source, Source.id == Item.source_id)
            .where(Source.source_type.like("github%"))
        )
    ).all()
    changed = 0
    for item, raw, source in rows:
        base_score = heuristic_final_score(source.tier, item.relevance_score, item.category)
        next_score = apply_source_specific_score(base_score, raw.extra, source.source_type)
        if next_score != item.final_score:
            item.final_score = next_score
            item.is_featured = item.is_ai_related and next_score >= 72
            changed += 1
    await db.commit()
    return {"seen": len(rows), "changed": changed}
