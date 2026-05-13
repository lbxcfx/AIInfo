from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.item import CrawlRunResult
from app.schemas.wechat import WechatDraftRead
from app.services.crawler import crawl_enabled_sources
from app.services.enrichment import enrich_items_batch, translate_titles_batch
from app.services.github_wechat import generate_github_wechat_draft
from app.services.llm import BigModelClient
from app.services.rescore import rescore_github_items
from app.services.search import reindex_items
from app.services.seed import seed_sources


router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/sources/seed")
async def seed_default_sources(db: AsyncSession = Depends(get_db)) -> ApiResponse[dict]:
    created = await seed_sources(db)
    return ApiResponse(data={"created": created})


@router.post("/crawl/run")
async def run_crawl(db: AsyncSession = Depends(get_db)) -> ApiResponse[CrawlRunResult]:
    result = await crawl_enabled_sources(db)
    return ApiResponse(data=CrawlRunResult.model_validate(result))


@router.post("/search/reindex")
async def rebuild_search_index(db: AsyncSession = Depends(get_db)) -> ApiResponse[dict]:
    result = await reindex_items(db)
    return ApiResponse(data=result)


@router.post("/items/enrich")
async def enrich_items(
    limit: int = 5,
    include_embeddings: bool = True,
    reindex_after: bool = True,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    result = await enrich_items_batch(
        db,
        limit=max(1, min(limit, 20)),
        include_embeddings=include_embeddings,
        reindex_after=reindex_after,
    )
    return ApiResponse(data=result)


@router.post("/items/translate-titles")
async def translate_titles(
    limit: int = 20,
    reindex_after: bool = True,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    result = await translate_titles_batch(
        db,
        limit=max(1, min(limit, 50)),
        reindex_after=reindex_after,
    )
    return ApiResponse(data=result)


@router.get("/models/ping")
async def ping_models() -> ApiResponse[dict]:
    client = BigModelClient()
    settings = client.settings
    models = [
        settings.llm_model_relevance,
        settings.llm_model_summary,
        settings.llm_model_audit,
    ]
    results = {}
    for model in models:
        try:
            results[model] = {"ok": "OK" in (await client.ping_chat(model))}
        except Exception as exc:
            results[model] = {"ok": False, "error": str(exc)}
    try:
        vector = await client.embed_one("AI 情报系统连通性测试")
        results[settings.embedding_model] = {
            "ok": len(vector) == settings.embedding_dimensions,
            "dimensions": len(vector),
        }
    except Exception as exc:
        results[settings.embedding_model] = {"ok": False, "error": str(exc)}
    return ApiResponse(data={"provider": settings.llm_provider, "models": results})


@router.post("/items/rescore-github")
async def rescore_github(db: AsyncSession = Depends(get_db)) -> ApiResponse[dict]:
    result = await rescore_github_items(db)
    result["reindex"] = await reindex_items(db)
    return ApiResponse(data=result)


@router.post("/github-wechat/drafts")
async def create_github_wechat_draft(
    item_id: str | None = None,
    submit: bool = True,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[WechatDraftRead]:
    try:
        draft = await generate_github_wechat_draft(db, item_id=item_id, submit=submit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(data=WechatDraftRead.model_validate(draft))
