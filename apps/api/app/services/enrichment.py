from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.text import clean_text, heuristic_final_score, stable_hash
from app.models.item import Item
from app.models.item_embedding import ItemEmbedding
from app.models.llm_call import LlmCall
from app.models.source import Source
from app.services.llm import BigModelClient
from app.services.search import reindex_items


PROMPT_VERSION = "ai-intel-enrich-v1"
ALLOWED_CATEGORIES = ["模型发布/更新", "产品发布/更新", "论文研究", "技巧与观点", "行业动态"]


def clamp_float(value: Any, default: float, *, lower: float = 0.0, upper: float = 100.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(lower, min(upper, number))


def normalize_category(value: Any, fallback: str) -> str:
    category = str(value or "").strip()
    return category if category in ALLOWED_CATEGORIES else fallback


def final_score_from_dimensions(source: Source, relevance: float, category: str, scores: dict[str, Any]) -> float:
    source_quality = scores.get("source_quality", source.reliability_score)
    weighted = (
        clamp_float(scores.get("novelty"), 55) * 0.24
        + clamp_float(scores.get("impact"), 55) * 0.25
        + clamp_float(scores.get("actionability"), 50) * 0.18
        + clamp_float(source_quality, source.reliability_score) * 0.18
        + clamp_float(scores.get("freshness"), 55) * 0.15
    )
    category_bonus = {
        "模型发布/更新": 5,
        "产品发布/更新": 4,
        "论文研究": 3,
        "技巧与观点": 1,
        "行业动态": 2,
    }.get(category, 2)
    relevance_gate = 0.72 + relevance * 0.28
    return round(min(99.0, weighted * relevance_gate + category_bonus), 1)


def build_enrichment_messages(item: Item, source: Source) -> list[dict[str, str]]:
    content = clean_text(item.content_text, 2400)
    user_payload = {
        "source": {"name": source.name, "tier": source.tier, "reliability_score": source.reliability_score},
        "title": item.title_original,
        "summary_or_content": content or item.summary_short,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "current_category": item.category,
    }
    return [
        {
            "role": "system",
            "content": (
                "你是AI情报分析员。只输出JSON对象，不要输出Markdown。"
                "根据输入判断是否AI相关，生成中文标题、短摘要、分类、实体和五维评分。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请输出以下字段："
                "title_zh: 中文标题; summary_short: 80-160字中文摘要; "
                "category: 必须是 模型发布/更新、产品发布/更新、论文研究、技巧与观点、行业动态 之一; "
                "entities: 包含 companies/products/models/people/papers/projects 数组; "
                "relevance_score: 0到1; "
                "scores: novelty/impact/actionability/source_quality/freshness 五项0到100; "
                "reason: 30字以内排序理由。\n\n"
                f"输入：{user_payload}"
            ),
        },
    ]


def build_title_translation_messages(item: Item) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "你是AI情报标题翻译助手。只输出JSON对象，不要输出Markdown。",
        },
        {
            "role": "user",
            "content": (
                "请把下面的英文AI情报标题翻译成简洁、准确、适合中文信息流展示的标题。"
                "保留公司名、模型名、仓库名、产品名，不要扩写事实。"
                '输出格式：{"title_zh":"..."}\n\n'
                f"英文标题：{item.title_original}"
            ),
        },
    ]


def apply_enrichment(item: Item, source: Source, payload: dict[str, Any]) -> None:
    relevance = clamp_float(payload.get("relevance_score"), item.relevance_score, upper=1.0)
    category = normalize_category(payload.get("category"), item.category)
    entities = payload.get("entities") if isinstance(payload.get("entities"), dict) else item.entities
    scores = payload.get("scores") if isinstance(payload.get("scores"), dict) else {}
    item.title_zh = clean_text(str(payload.get("title_zh") or item.title_zh or ""), 240) or item.title_zh
    item.summary_short = clean_text(str(payload.get("summary_short") or item.summary_short), 320)
    item.category = category
    item.entities = entities
    item.relevance_score = relevance
    item.score_details = {
        "model_scores": scores,
        "reason": clean_text(str(payload.get("reason") or ""), 120),
        "prompt_version": PROMPT_VERSION,
    }
    item.final_score = final_score_from_dimensions(source, relevance, category, scores)
    if not scores:
        item.final_score = heuristic_final_score(source.tier, relevance, category)
    item.is_ai_related = relevance >= 0.5
    item.is_featured = item.final_score >= 72 and item.is_ai_related
    item.processing_status = "llm_processed"
    item.llm_processed_at = datetime.now(timezone.utc)


async def record_llm_call(
    db: AsyncSession,
    *,
    item_id: str | None,
    task: str,
    model: str,
    input_hash: str,
    status: str,
    latency_ms: int | None = None,
    token_usage: dict[str, Any] | None = None,
    output_json: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    db.add(
        LlmCall(
            item_id=item_id,
            task=task,
            model=model,
            prompt_version=PROMPT_VERSION,
            input_hash=input_hash,
            status=status,
            latency_ms=latency_ms,
            token_usage=token_usage or {},
            output_json=output_json or {},
            error_message=error_message,
        )
    )


async def enrich_item(db: AsyncSession, item: Item, source: Source, client: BigModelClient) -> dict[str, Any]:
    settings = get_settings()
    input_hash = stable_hash(item.id, item.title_original, item.content_text[:2000], PROMPT_VERSION)
    started = time.perf_counter()
    try:
        payload, usage = await client.chat_json(
            model=settings.llm_model_scoring,
            messages=build_enrichment_messages(item, source),
            temperature=settings.llm_temperature_scoring,
            max_tokens=settings.llm_max_tokens_scoring,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        apply_enrichment(item, source, payload)
        await record_llm_call(
            db,
            item_id=item.id,
            task="item_enrichment",
            model=settings.llm_model_scoring,
            input_hash=input_hash,
            status="ok",
            latency_ms=latency_ms,
            token_usage=usage,
            output_json=payload,
        )
        return {"item_id": item.id, "status": "ok", "latency_ms": latency_ms}
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        item.processing_status = "llm_failed"
        await record_llm_call(
            db,
            item_id=item.id,
            task="item_enrichment",
            model=settings.llm_model_scoring,
            input_hash=input_hash,
            status="error",
            latency_ms=latency_ms,
            error_message=str(exc),
        )
        return {"item_id": item.id, "status": "error", "error": str(exc)}


async def translate_item_title(db: AsyncSession, item: Item, client: BigModelClient) -> dict[str, Any]:
    settings = get_settings()
    input_hash = stable_hash(item.id, item.title_original, "title_translation", PROMPT_VERSION)
    started = time.perf_counter()
    try:
        payload, usage = await client.chat_json(
            model=settings.llm_model_translation,
            messages=build_title_translation_messages(item),
            temperature=settings.llm_temperature_classification,
            max_tokens=settings.llm_max_tokens_relevance,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        title_zh = clean_text(str(payload.get("title_zh") or ""), 240)
        if not title_zh:
            raise ValueError("title_zh is empty")
        item.title_zh = title_zh
        await record_llm_call(
            db,
            item_id=item.id,
            task="title_translation",
            model=settings.llm_model_translation,
            input_hash=input_hash,
            status="ok",
            latency_ms=latency_ms,
            token_usage=usage,
            output_json={"title_zh": title_zh},
        )
        return {"item_id": item.id, "status": "ok", "latency_ms": latency_ms}
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        await record_llm_call(
            db,
            item_id=item.id,
            task="title_translation",
            model=settings.llm_model_translation,
            input_hash=input_hash,
            status="error",
            latency_ms=latency_ms,
            error_message=str(exc),
        )
        return {"item_id": item.id, "status": "error", "error": str(exc)}


async def embed_item(db: AsyncSession, item: Item, client: BigModelClient) -> dict[str, Any]:
    settings = get_settings()
    text = clean_text(f"{item.title_zh or item.title_original}\n{item.summary_short}", 3000)
    content_hash = stable_hash(text, settings.embedding_model, str(settings.embedding_dimensions))
    existing = (
        await db.execute(select(ItemEmbedding).where(ItemEmbedding.item_id == item.id))
    ).scalar_one_or_none()
    if existing and existing.content_hash == content_hash:
        return {"item_id": item.id, "status": "cached"}
    vector = await client.embed_one(text)
    stmt = insert(ItemEmbedding).values(
        item_id=item.id,
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        content_hash=content_hash,
        embedding=vector,
        text_preview=clean_text(text, 500),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[ItemEmbedding.item_id],
        set_={
            "model": settings.embedding_model,
            "dimensions": settings.embedding_dimensions,
            "content_hash": content_hash,
            "embedding": vector,
            "text_preview": clean_text(text, 500),
        },
    )
    await db.execute(stmt)
    return {"item_id": item.id, "status": "ok"}


async def enrich_items_batch(
    db: AsyncSession,
    *,
    limit: int = 5,
    include_embeddings: bool = True,
    reindex_after: bool = True,
) -> dict[str, Any]:
    stmt = (
        select(Item, Source)
        .join(Source, Source.id == Item.source_id)
        .where(Item.is_ai_related.is_(True), Item.llm_processed_at.is_(None))
        .order_by(desc(Item.final_score), desc(Item.published_at).nullslast())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    client = BigModelClient()
    results: list[dict[str, Any]] = []
    embedding_results: list[dict[str, Any]] = []
    for item, source in rows:
        result = await enrich_item(db, item, source, client)
        results.append(result)
        if include_embeddings and result["status"] == "ok":
            try:
                embedding_results.append(await embed_item(db, item, client))
            except Exception as exc:
                embedding_results.append({"item_id": item.id, "status": "error", "error": str(exc)})
    await db.commit()
    reindex_result = await reindex_items(db) if reindex_after and rows else None
    return {
        "seen": len(rows),
        "processed": sum(1 for result in results if result["status"] == "ok"),
        "failed": sum(1 for result in results if result["status"] == "error"),
        "results": results,
        "embeddings": embedding_results,
        "reindex": reindex_result,
    }


async def translate_titles_batch(
    db: AsyncSession,
    *,
    limit: int = 20,
    reindex_after: bool = True,
) -> dict[str, Any]:
    stmt = (
        select(Item)
        .where(Item.is_ai_related.is_(True), or_(Item.title_zh.is_(None), Item.title_zh == ""))
        .order_by(desc(Item.published_at).nullslast(), desc(Item.final_score))
        .limit(limit)
    )
    items = (await db.execute(stmt)).scalars().all()
    client = BigModelClient()
    results: list[dict[str, Any]] = []
    for item in items:
        results.append(await translate_item_title(db, item, client))
    await db.commit()
    reindex_result = await reindex_items(db) if reindex_after and items else None
    return {
        "seen": len(items),
        "translated": sum(1 for result in results if result["status"] == "ok"),
        "failed": sum(1 for result in results if result["status"] == "error"),
        "results": results,
        "reindex": reindex_result,
    }
