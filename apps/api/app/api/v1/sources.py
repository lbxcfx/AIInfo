from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.source import Source
from app.models.source_health import SourceHealth
from app.schemas.common import ApiResponse
from app.schemas.source import SourceCreate, SourceRead, SourceUpdate


router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("")
async def list_sources(db: AsyncSession = Depends(get_db)) -> ApiResponse[list[SourceRead]]:
    result = await db.execute(select(Source).order_by(Source.created_at.desc()))
    sources = result.scalars().all()
    return ApiResponse(data=[SourceRead.model_validate(source) for source in sources])


@router.get("/health/summary")
async def source_health_summary(db: AsyncSession = Depends(get_db)) -> ApiResponse[list[dict]]:
    sources = (await db.execute(select(Source).order_by(Source.tier, Source.name))).scalars().all()
    data = []
    for source in sources:
        health = (
            await db.execute(
                select(SourceHealth)
                .where(SourceHealth.source_id == source.id)
                .order_by(desc(SourceHealth.checked_at))
                .limit(1)
            )
        ).scalar_one_or_none()
        data.append(
            {
                "source": SourceRead.model_validate(source).model_dump(mode="json"),
                "latest_health": {
                    "status": health.status,
                    "checked_at": health.checked_at.isoformat(),
                    "fetched_count": health.fetched_count,
                    "new_count": health.new_count,
                    "error_message": health.error_message,
                }
                if health
                else None,
            }
        )
    return ApiResponse(data=data)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: SourceCreate, db: AsyncSession = Depends(get_db)
) -> ApiResponse[SourceRead]:
    source = Source(**payload.model_dump(mode="json"))
    db.add(source)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="source url already exists") from exc
    await db.refresh(source)
    return ApiResponse(data=SourceRead.model_validate(source))


@router.get("/{source_id}")
async def get_source(source_id: str, db: AsyncSession = Depends(get_db)) -> ApiResponse[SourceRead]:
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="source not found")
    return ApiResponse(data=SourceRead.model_validate(source))


@router.patch("/{source_id}")
async def update_source(
    source_id: str, payload: SourceUpdate, db: AsyncSession = Depends(get_db)
) -> ApiResponse[SourceRead]:
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="source not found")
    for key, value in payload.model_dump(exclude_unset=True, mode="json").items():
        setattr(source, key, value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="source url already exists") from exc
    await db.refresh(source)
    return ApiResponse(data=SourceRead.model_validate(source))
