from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx
import re
from html import unescape
from urllib.parse import urljoin, urlsplit, urlunsplit
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.text import (
    ai_relevance_score,
    canonicalize_url,
    classify_category,
    clean_text,
    heuristic_final_score,
    stable_hash,
)
from app.models.item import Item
from app.models.raw_item import RawItem
from app.models.source import Source
from app.models.source_health import SourceHealth


def parse_entry_datetime(entry: Any) -> datetime | None:
    for key in ("published", "updated", "created"):
        value = entry.get(key)
        if not value:
            continue
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            continue
    parsed_struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed_struct:
        return datetime(*parsed_struct[:6], tzinfo=timezone.utc)
    return None


def entry_content(entry: Any) -> str:
    if entry.get("content"):
        parts = [part.get("value", "") for part in entry.get("content", [])]
        return clean_text(" ".join(parts), 4000)
    return clean_text(entry.get("summary") or entry.get("description"), 4000)


def html_attr(html: str, pattern: str) -> str:
    match = re.search(pattern, html, flags=re.I | re.S)
    return unescape(match.group(1)).strip() if match else ""


def html_title(html: str) -> str:
    return clean_text(html_attr(html, r"<title[^>]*>(.*?)</title>"), 500)


def html_meta_description(html: str) -> str:
    for pattern in (
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']',
    ):
        value = html_attr(html, pattern)
        if value:
            return clean_text(value, 1000)
    return ""


def html_published_at(html: str) -> datetime | None:
    for pattern in (
        r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
        r'<time[^>]+datetime=["\']([^"\']+)["\']',
        r"&quot;date&quot;:\[3,&quot;([^&]+)&quot;\]",
    ):
        value = html_attr(html, pattern)
        if not value:
            continue
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def extract_page_links(html: str, base_url: str, prefixes: list[str], limit: int) -> list[str]:
    links: list[str] = []
    base_parts = urlsplit(base_url)
    origin = urlunsplit((base_parts.scheme, base_parts.netloc, "", "", ""))
    for match in re.finditer(r'href=["\']([^"\']+)["\']', html):
        href = unescape(match.group(1)).split("#", 1)[0].strip()
        absolute_url = urljoin(base_url, href)
        parts = urlsplit(absolute_url)
        if parts.netloc != base_parts.netloc:
            continue
        path = parts.path
        if not path.startswith("/"):
            continue
        if not any(path.startswith(prefix) or absolute_url.startswith(prefix) for prefix in prefixes):
            continue
        url = origin + path.rstrip("/")
        if url not in links and url != base_url.rstrip("/"):
            links.append(url)
        if len(links) >= limit:
            break
    return links


def build_item(raw: RawItem, source: Source) -> Item:
    relevance = ai_relevance_score(raw.raw_title, raw.raw_content)
    category = classify_category(raw.raw_title, raw.raw_content)
    final_score = apply_source_specific_score(
        heuristic_final_score(source.tier, relevance, category), raw.extra, source.source_type
    )
    return Item(
        raw_id=raw.id,
        source_id=raw.source_id,
        canonical_url=canonicalize_url(raw.raw_url),
        title_original=raw.raw_title,
        title_zh=None,
        content_text=raw.raw_content,
        summary_short=clean_text(raw.raw_content, 220) or raw.raw_title,
        language=source.language,
        category=category,
        entities={"source": source.name},
        published_at=raw.published_at,
        is_ai_related=relevance >= 0.45,
        relevance_score=relevance,
        final_score=final_score,
        is_featured=final_score >= 68 and relevance >= 0.45,
    )


def apply_source_specific_score(base_score: float, extra: dict[str, Any], source_type: str) -> float:
    if source_type.startswith("huggingface"):
        likes = int(extra.get("likes") or 0)
        downloads = int(extra.get("downloads") or 0)
        trending_rank = int(extra.get("trending_rank") or 0)
        metric_boost = 0.0
        if downloads >= 100000:
            metric_boost += 7
        elif downloads >= 10000:
            metric_boost += 4
        elif downloads >= 1000:
            metric_boost += 2
        if likes >= 1000:
            metric_boost += 6
        elif likes >= 200:
            metric_boost += 3
        elif likes < 20:
            metric_boost -= 4
        if trending_rank:
            metric_boost += max(0, 6 - trending_rank * 0.15)
        return round(max(30.0, min(99.0, base_score + metric_boost)), 1)
    if not source_type.startswith("github"):
        return base_score
    stars = int(extra.get("stars") or 0)
    forks = int(extra.get("forks") or 0)
    trending_rank = int(extra.get("trending_rank") or 0)
    stars_today = int(extra.get("stars_today") or 0)
    metric_boost = 0.0
    if stars >= 1000:
        metric_boost += 6
    elif stars >= 500:
        metric_boost += 3
    elif stars < 200:
        metric_boost -= 8
    if forks >= 100:
        metric_boost += 4
    elif forks < 30:
        metric_boost -= 5
    if trending_rank:
        metric_boost += max(0, 5 - trending_rank * 0.12)
    if stars_today:
        metric_boost += min(6, stars_today / 20)
    score = round(max(30.0, min(99.0, base_score + metric_boost)), 1)
    if stars < 200 and forks < 30 and stars_today < 80:
        return min(score, 65.0)
    if stars < 500 and forks < 50 and stars_today < 150:
        return min(score, 72.0)
    return score


def extract_repo_slugs(html: str, limit: int) -> list[str]:
    slugs: list[str] = []
    excluded_owners = {
        "about",
        "collections",
        "customer-stories",
        "enterprise",
        "events",
        "explore",
        "features",
        "github",
        "login",
        "marketplace",
        "new",
        "orgs",
        "pricing",
        "search",
        "security",
        "signup",
        "sponsors",
        "topics",
        "trending",
    }
    pattern = re.compile(r'href="/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"')
    for match in pattern.finditer(html):
        slug = match.group(1)
        owner, repo = slug.split("/", 1)
        if owner.lower() in excluded_owners or repo.lower() in {"explore", "new", "sponsors"}:
            continue
        if slug not in slugs:
            slugs.append(slug)
        if len(slugs) >= limit:
            break
    return slugs


def extract_stars_today(html: str, slug: str) -> int:
    owner, repo = slug.split("/", 1)
    repo_pattern = re.compile(
        rf'{re.escape(owner)}\s*</a>\s*/\s*.*?{re.escape(repo)}.*?(\d[\d,]*)\s+stars\s+today',
        flags=re.S | re.I,
    )
    match = repo_pattern.search(html)
    if not match:
        return 0
    return int(match.group(1).replace(",", ""))


def github_recent_query(query: str, recent_days: int) -> str:
    if re.search(r"\b(created|pushed|updated):", query):
        return query
    since = (datetime.now(timezone.utc) - timedelta(days=recent_days)).date().isoformat()
    return f"{query} pushed:>={since}"


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


async def fetch_github_repo(client: httpx.AsyncClient, slug: str, headers: dict[str, str]) -> dict[str, Any] | None:
    response = await client.get(f"https://api.github.com/repos/{slug}", headers=headers)
    if response.status_code in {403, 404, 429}:
        return None
    response.raise_for_status()
    return response.json()


def github_headers() -> dict[str, str]:
    settings = get_settings()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AIIntelRadarBot/0.1 (+local-dev)",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


async def persist_raw_item(
    db: AsyncSession,
    *,
    source: Source,
    raw_url: str,
    fetched_url: str,
    raw_title: str,
    raw_content: str,
    published_at: datetime | None,
    http_status: int | None,
    extra: dict[str, Any] | None = None,
) -> bool:
    if not raw_url or not raw_title:
        return False
    canonical_url = canonicalize_url(raw_url)
    existing_raw = await db.execute(
        select(RawItem.id).where(RawItem.source_id == source.id, RawItem.raw_url == canonical_url)
    )
    if existing_raw.scalar_one_or_none():
        return False
    existing_item = await db.execute(select(Item.id).where(Item.canonical_url == canonical_url))
    if existing_item.scalar_one_or_none():
        return False
    raw = RawItem(
        source_id=source.id,
        raw_url=canonical_url,
        fetched_url=fetched_url,
        raw_title=clean_text(raw_title, 500),
        raw_content=clean_text(raw_content, 4000),
        published_at=published_at,
        http_status=http_status,
        content_hash=stable_hash(canonical_url, raw_title),
        extra=extra or {},
    )
    db.add(raw)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return False

    item = build_item(raw, source)
    db.add(item)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return False
    return True


async def crawl_rss_source(db: AsyncSession, source: Source) -> tuple[int, int, str | None]:
    settings = get_settings()
    source_id = source.id
    fetched_count = 0
    created_count = 0
    error_message = None
    try:
        async with httpx.AsyncClient(timeout=settings.bigmodel_timeout_seconds, follow_redirects=True) as client:
            response = await client.get(
                source.url,
                headers={"User-Agent": "AIIntelRadarBot/0.1 (+local-dev)"},
            )
            response.raise_for_status()
        feed = feedparser.parse(response.content)
        fetched_count = len(feed.entries)
        for entry in feed.entries[:30]:
            raw_url = entry.get("link") or entry.get("id")
            raw_title = clean_text(entry.get("title"), 500)
            if not raw_url or not raw_title:
                continue
            created = await persist_raw_item(
                db,
                source=source,
                raw_url=raw_url,
                fetched_url=str(response.url),
                raw_title=raw_title,
                raw_content=entry_content(entry),
                published_at=parse_entry_datetime(entry),
                http_status=response.status_code,
                extra={"feed_id": entry.get("id")},
            )
            if created:
                created_count += 1
        await db.commit()
    except Exception as exc:
        await db.rollback()
        error_message = str(exc) or exc.__class__.__name__
    db.add(
        SourceHealth(
            source_id=source_id,
            checked_at=datetime.now(timezone.utc),
            status="ok" if error_message is None else "error",
            fetched_count=fetched_count,
            new_count=created_count,
            error_message=error_message,
        )
    )
    await db.commit()
    return fetched_count, created_count, error_message


async def crawl_web_page_list_source(db: AsyncSession, source: Source) -> tuple[int, int, str | None]:
    settings = get_settings()
    source_id = source.id
    fetched_count = 0
    created_count = 0
    error_message = None
    prefixes = source.extra.get("link_prefixes") or ["/blog/"]
    max_items = int(source.extra.get("max_items") or 20)
    try:
        async with httpx.AsyncClient(timeout=settings.bigmodel_timeout_seconds, follow_redirects=True, trust_env=False) as client:
            list_response = await client.get(
                source.url,
                headers={"User-Agent": "AIIntelRadarBot/0.1 (+local-dev)"},
            )
            list_response.raise_for_status()
            links = extract_page_links(list_response.text, source.url, prefixes, max_items)
            for link in links:
                response = await client.get(
                    link,
                    headers={"User-Agent": "AIIntelRadarBot/0.1 (+local-dev)"},
                )
                response.raise_for_status()
                fetched_count += 1
                title = html_title(response.text)
                description = html_meta_description(response.text)
                if not title:
                    title = link.rsplit("/", 1)[-1].replace("-", " ").title()
                created = await persist_raw_item(
                    db,
                    source=source,
                    raw_url=link,
                    fetched_url=str(list_response.url),
                    raw_title=title,
                    raw_content=description or title,
                    published_at=html_published_at(response.text) or datetime.now(timezone.utc),
                    http_status=response.status_code,
                    extra={"list_url": source.url, "description": description},
                )
                if created:
                    created_count += 1
        await db.commit()
    except Exception as exc:
        await db.rollback()
        error_message = str(exc) or exc.__class__.__name__
    db.add(
        SourceHealth(
            source_id=source_id,
            checked_at=datetime.now(timezone.utc),
            status="ok" if error_message is None else "error",
            fetched_count=fetched_count,
            new_count=created_count,
            error_message=error_message,
        )
    )
    await db.commit()
    return fetched_count, created_count, error_message


async def crawl_github_trending_source(db: AsyncSession, source: Source) -> tuple[int, int, str | None]:
    source_id = source.id
    fetched_count = 0
    created_count = 0
    error_message = None
    queries = source.extra.get("queries") or ["topic:artificial-intelligence stars:>50"]
    per_page = int(source.extra.get("per_page") or 12)
    sort = source.extra.get("sort") or "stars"
    headers = github_headers()
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, trust_env=False) as client:
            for query in queries:
                response = await client.get(
                    "https://api.github.com/search/repositories",
                    params={
                        "q": github_recent_query(query, int(source.extra.get("recent_days") or 7)),
                        "sort": sort,
                        "order": "desc",
                        "per_page": per_page,
                    },
                    headers=headers,
                )
                response.raise_for_status()
                payload = response.json()
                for repo in payload.get("items", []):
                    fetched_count += 1
                    stars = repo.get("stargazers_count") or 0
                    forks = repo.get("forks_count") or 0
                    updated_at = repo.get("updated_at")
                    pushed_at = repo.get("pushed_at")
                    published_at = None
                    for value in (pushed_at, updated_at):
                        if value:
                            published_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
                            break
                    description = repo.get("description") or ""
                    topics = ", ".join(repo.get("topics") or [])
                    content = (
                        f"GitHub 仓库趋势信号。stars: {stars}; forks: {forks}; "
                        f"language: {repo.get('language') or 'unknown'}; topics: {topics}. {description}"
                    )
                    created = await persist_raw_item(
                        db,
                        source=source,
                        raw_url=repo.get("html_url") or repo.get("url"),
                        fetched_url=str(response.url),
                        raw_title=f"{repo.get('full_name')}: {description or 'AI repository'}",
                        raw_content=content,
                        published_at=published_at,
                        http_status=response.status_code,
                        extra={
                            "stars": stars,
                            "forks": forks,
                            "language": repo.get("language"),
                            "topics": repo.get("topics") or [],
                            "query": query,
                        },
                    )
                    if created:
                        created_count += 1
        await db.commit()
    except Exception as exc:
        await db.rollback()
        error_message = str(exc) or exc.__class__.__name__
    db.add(
        SourceHealth(
            source_id=source_id,
            checked_at=datetime.now(timezone.utc),
            status="ok" if error_message is None else "error",
            fetched_count=fetched_count,
            new_count=created_count,
            error_message=error_message,
        )
    )
    await db.commit()
    return fetched_count, created_count, error_message


async def crawl_github_page_source(db: AsyncSession, source: Source) -> tuple[int, int, str | None]:
    source_id = source.id
    fetched_count = 0
    created_count = 0
    error_message = None
    urls = source.extra.get("urls") or [source.url]
    max_repos = int(source.extra.get("max_repos") or 20)
    headers = github_headers()
    page_headers = {"User-Agent": "AIIntelRadarBot/0.1 (+local-dev)"}
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, trust_env=False) as client:
            for page_url in urls:
                page_response = await client.get(page_url, headers=page_headers)
                page_response.raise_for_status()
                slugs = extract_repo_slugs(page_response.text, max_repos)
                for rank, slug in enumerate(slugs, start=1):
                    repo = await fetch_github_repo(client, slug, headers)
                    if not repo:
                        continue
                    fetched_count += 1
                    stars = repo.get("stargazers_count") or 0
                    forks = repo.get("forks_count") or 0
                    updated_at = repo.get("updated_at")
                    pushed_at = repo.get("pushed_at")
                    published_at = None
                    for value in (pushed_at, updated_at):
                        if value:
                            published_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
                            break
                    topics = ", ".join(repo.get("topics") or [])
                    stars_today = extract_stars_today(page_response.text, slug)
                    description = repo.get("description") or ""
                    content = (
                        f"GitHub 官方页面发现信号。rank: {rank}; stars today: {stars_today}; "
                        f"stars: {stars}; forks: {forks}; language: {repo.get('language') or 'unknown'}; "
                        f"topics: {topics}. {description}"
                    )
                    created = await persist_raw_item(
                        db,
                        source=source,
                        raw_url=repo.get("html_url") or f"https://github.com/{slug}",
                        fetched_url=str(page_response.url),
                        raw_title=f"{repo.get('full_name')}: {description or 'GitHub repository'}",
                        raw_content=content,
                        published_at=published_at,
                        http_status=page_response.status_code,
                        extra={
                            "stars": stars,
                            "forks": forks,
                            "language": repo.get("language"),
                            "topics": repo.get("topics") or [],
                            "trending_rank": rank if source.source_type == "github_trending_page" else None,
                            "stars_today": stars_today,
                            "discovery_url": page_url,
                        },
                    )
                    if created:
                        created_count += 1
        await db.commit()
    except Exception as exc:
        await db.rollback()
        error_message = str(exc) or exc.__class__.__name__
    db.add(
        SourceHealth(
            source_id=source_id,
            checked_at=datetime.now(timezone.utc),
            status="ok" if error_message is None else "error",
            fetched_count=fetched_count,
            new_count=created_count,
            error_message=error_message,
        )
    )
    await db.commit()
    return fetched_count, created_count, error_message


async def crawl_huggingface_trending_source(db: AsyncSession, source: Source) -> tuple[int, int, str | None]:
    source_id = source.id
    fetched_count = 0
    created_count = 0
    error_message = None
    repo_type = source.extra.get("repo_type") or "models"
    api_paths = {
        "models": "/api/models",
        "datasets": "/api/datasets",
        "spaces": "/api/spaces",
    }
    page_prefixes = {
        "models": "",
        "datasets": "/datasets",
        "spaces": "/spaces",
    }
    api_path = api_paths.get(repo_type, "/api/models")
    page_prefix = page_prefixes.get(repo_type, "")
    limit = int(source.extra.get("limit") or 30)
    sort = source.extra.get("sort") or "trending"
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, trust_env=False) as client:
            response = await client.get(
                f"https://huggingface.co{api_path}",
                params={"sort": sort, "direction": -1, "limit": limit, "full": True},
                headers={"User-Agent": "AIIntelRadarBot/0.1 (+local-dev)"},
            )
            response.raise_for_status()
            payload = response.json()
            repos = payload if isinstance(payload, list) else payload.get("items", [])
            for rank, repo in enumerate(repos[:limit], start=1):
                repo_id = repo.get("id") or repo.get("modelId")
                if not repo_id:
                    continue
                fetched_count += 1
                tags = repo.get("tags") or []
                card_data = repo.get("cardData") or {}
                description = (
                    repo.get("description")
                    or card_data.get("description")
                    or card_data.get("summary")
                    or f"Hugging Face trending {repo_type[:-1] if repo_type.endswith('s') else repo_type}"
                )
                likes = int(repo.get("likes") or 0)
                downloads = int(repo.get("downloads") or 0)
                task = repo.get("pipeline_tag") or repo.get("sdk") or card_data.get("task") or "unknown"
                content = (
                    f"Hugging Face 趋势信号。repo_type: {repo_type}; rank: {rank}; "
                    f"downloads: {downloads}; likes: {likes}; task: {task}; tags: {', '.join(tags[:12])}. "
                    f"{description}"
                )
                published_at = (
                    parse_iso_datetime(repo.get("lastModified"))
                    or parse_iso_datetime(repo.get("createdAt"))
                    or datetime.now(timezone.utc)
                )
                created = await persist_raw_item(
                    db,
                    source=source,
                    raw_url=f"https://huggingface.co{page_prefix}/{repo_id}",
                    fetched_url=str(response.url),
                    raw_title=f"{repo_id}: {description}",
                    raw_content=content,
                    published_at=published_at,
                    http_status=response.status_code,
                    extra={
                        "repo_type": repo_type,
                        "downloads": downloads,
                        "likes": likes,
                        "task": task,
                        "tags": tags,
                        "trending_rank": rank,
                    },
                )
                if created:
                    created_count += 1
        await db.commit()
    except Exception as exc:
        await db.rollback()
        error_message = str(exc) or exc.__class__.__name__
    db.add(
        SourceHealth(
            source_id=source_id,
            checked_at=datetime.now(timezone.utc),
            status="ok" if error_message is None else "error",
            fetched_count=fetched_count,
            new_count=created_count,
            error_message=error_message,
        )
    )
    await db.commit()
    return fetched_count, created_count, error_message


async def crawl_x_recent_source(db: AsyncSession, source: Source) -> tuple[int, int, str | None]:
    settings = get_settings()
    source_id = source.id
    if not settings.x_bearer_token:
        error_message = "X_BEARER_TOKEN 未配置，X/Twitter 热议源保持待启用状态。"
        db.add(
            SourceHealth(
                source_id=source_id,
                checked_at=datetime.now(timezone.utc),
                status="skipped",
                fetched_count=0,
                new_count=0,
                error_message=error_message,
            )
        )
        await db.commit()
        return 0, 0, error_message
    fetched_count = 0
    created_count = 0
    error_message = None
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(timespec="seconds").replace("+00:00", "Z")
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, trust_env=False) as client:
            response = await client.get(
                "https://api.twitter.com/2/tweets/search/recent",
                params={
                    "query": source.extra.get("query") or "(AI OR LLM OR OpenAI OR agent) -is:retweet lang:en",
                    "max_results": 25,
                    "start_time": since,
                    "tweet.fields": "created_at,public_metrics,author_id,lang",
                },
                headers={"Authorization": f"Bearer {settings.x_bearer_token}"},
            )
            response.raise_for_status()
            payload = response.json()
            for tweet in payload.get("data", []):
                fetched_count += 1
                metrics = tweet.get("public_metrics") or {}
                text = clean_text(tweet.get("text"), 500)
                tweet_id = tweet.get("id")
                created_at = tweet.get("created_at")
                published_at = datetime.fromisoformat(created_at.replace("Z", "+00:00")) if created_at else None
                score_hint = (
                    f"retweets: {metrics.get('retweet_count', 0)}; "
                    f"likes: {metrics.get('like_count', 0)}; replies: {metrics.get('reply_count', 0)}"
                )
                created = await persist_raw_item(
                    db,
                    source=source,
                    raw_url=f"https://twitter.com/i/web/status/{tweet_id}",
                    fetched_url=str(response.url),
                    raw_title=text,
                    raw_content=f"X/Twitter AI 热议信号。{score_hint}. {text}",
                    published_at=published_at,
                    http_status=response.status_code,
                    extra={"tweet_id": tweet_id, "metrics": metrics, "author_id": tweet.get("author_id")},
                )
                if created:
                    created_count += 1
        await db.commit()
    except Exception as exc:
        await db.rollback()
        error_message = str(exc) or exc.__class__.__name__
    db.add(
        SourceHealth(
            source_id=source_id,
            checked_at=datetime.now(timezone.utc),
            status="ok" if error_message is None else "error",
            fetched_count=fetched_count,
            new_count=created_count,
            error_message=error_message,
        )
    )
    await db.commit()
    return fetched_count, created_count, error_message


async def crawl_enabled_sources(db: AsyncSession) -> dict[str, Any]:
    result = await db.execute(
        select(Source).where(Source.is_enabled.is_(True)).order_by(Source.tier, Source.name)
    )
    sources = result.scalars().all()
    raw_created = 0
    errors: list[str] = []
    for source in sources:
        source_name = source.name
        source_type = source.source_type
        if source.source_type == "rss":
            _, created, error = await crawl_rss_source(db, source)
        elif source.source_type == "web_page_list":
            _, created, error = await crawl_web_page_list_source(db, source)
        elif source.source_type == "github_trending":
            _, created, error = await crawl_github_trending_source(db, source)
        elif source.source_type in {"github_trending_page", "github_topic_page"}:
            _, created, error = await crawl_github_page_source(db, source)
        elif source.source_type == "huggingface_trending":
            _, created, error = await crawl_huggingface_trending_source(db, source)
        elif source.source_type == "x_recent_search":
            _, created, error = await crawl_x_recent_source(db, source)
        else:
            continue
        raw_created += created
        if error:
            errors.append(f"{source_name}: {error}")
    return {
        "sources_seen": len(sources),
        "raw_created": raw_created,
        "items_created": raw_created,
        "errors": errors,
    }
