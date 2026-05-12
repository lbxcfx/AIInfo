import httpx
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings


async def check_database(db: AsyncSession) -> dict:
    result = await db.execute(text("select 1"))
    return {"ok": result.scalar_one() == 1}


async def check_redis() -> dict:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url)
    try:
        pong = await redis.ping()
        return {"ok": bool(pong)}
    finally:
        await redis.aclose()


async def check_meilisearch() -> dict:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(
            f"{settings.meilisearch_url.rstrip('/')}/health",
            headers={"Authorization": f"Bearer {settings.meilisearch_master_key}"},
        )
        response.raise_for_status()
        payload = response.json()
        return {"ok": payload.get("status") == "available", "status": payload.get("status")}

