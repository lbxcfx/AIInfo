from fastapi import APIRouter

from app.api.v1 import admin, daily, health, items, search, sources


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(sources.router)
api_router.include_router(items.router)
api_router.include_router(search.router)
api_router.include_router(daily.router)
api_router.include_router(admin.router)
