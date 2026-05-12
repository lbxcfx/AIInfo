from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.services.health import check_database, check_meilisearch, check_redis


router = APIRouter(tags=["health"])


@router.get("/health")
async def api_health(db: AsyncSession = Depends(get_db)) -> ApiResponse[dict]:
    settings = get_settings()
    checks: dict[str, dict] = {"app": {"ok": True, "env": settings.app_env}}
    for name, checker in {
        "database": lambda: check_database(db),
        "redis": check_redis,
        "meilisearch": check_meilisearch,
    }.items():
        try:
            checks[name] = await checker()
        except Exception as exc:  # pragma: no cover - exposed for operator diagnostics
            checks[name] = {"ok": False, "error": str(exc)}
    return ApiResponse(data={"status": "ok", "checks": checks})

