from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.source import Source


SEED_SOURCES = [
    {
        "name": "OpenAI News",
        "url": "https://openai.com/news/rss.xml",
        "source_type": "rss",
        "tier": "T1",
        "language": "en",
        "category_hint": "模型发布/更新",
        "crawl_interval_minutes": 30,
        "reliability_score": 95,
    },
    {
        "name": "Anthropic News",
        "url": "https://www.anthropic.com/news",
        "source_type": "web_page_list",
        "tier": "T1",
        "language": "en",
        "category_hint": "模型发布/更新",
        "crawl_interval_minutes": 120,
        "reliability_score": 94,
        "extra": {"link_prefixes": ["/news/"], "max_items": 16},
    },
    {
        "name": "Anthropic Engineering",
        "url": "https://www.anthropic.com/engineering",
        "source_type": "web_page_list",
        "tier": "T1",
        "language": "en",
        "category_hint": "技巧与观点",
        "crawl_interval_minutes": 180,
        "reliability_score": 94,
        "extra": {"link_prefixes": ["/engineering/"], "max_items": 16},
    },
    {
        "name": "Anthropic Research",
        "url": "https://www.anthropic.com/research",
        "source_type": "web_page_list",
        "tier": "T1",
        "language": "en",
        "category_hint": "论文研究",
        "crawl_interval_minutes": 180,
        "reliability_score": 94,
        "extra": {"link_prefixes": ["/research/"], "max_items": 16},
    },
    {
        "name": "Sam Altman Blog",
        "url": "https://blog.samaltman.com/posts.atom",
        "source_type": "rss",
        "tier": "T1",
        "language": "en",
        "category_hint": "行业动态",
        "crawl_interval_minutes": 240,
        "reliability_score": 88,
    },
    {
        "name": "Hugging Face Blog",
        "url": "https://huggingface.co/blog/feed.xml",
        "source_type": "rss",
        "tier": "T1",
        "language": "en",
        "category_hint": "产品发布/更新",
        "crawl_interval_minutes": 60,
        "reliability_score": 92,
    },
    {
        "name": "Google DeepMind News",
        "url": "https://deepmind.google/blog/rss.xml",
        "source_type": "rss",
        "tier": "T1",
        "language": "en",
        "category_hint": "论文研究",
        "crawl_interval_minutes": 120,
        "reliability_score": 93,
    },
    {
        "name": "Microsoft AI Blog",
        "url": "https://blogs.microsoft.com/ai/feed/",
        "source_type": "rss",
        "tier": "T1_5",
        "language": "en",
        "category_hint": "行业动态",
        "crawl_interval_minutes": 120,
        "reliability_score": 86,
    },
    {
        "name": "Apple Newsroom",
        "url": "https://www.apple.com/newsroom/rss-feed.rss",
        "source_type": "rss",
        "tier": "T1_5",
        "language": "en",
        "category_hint": "行业动态",
        "crawl_interval_minutes": 240,
        "reliability_score": 84,
    },
    {
        "name": "Google AI Blog",
        "url": "https://blog.google/technology/ai/rss/",
        "source_type": "rss",
        "tier": "T1",
        "language": "en",
        "category_hint": "行业动态",
        "crawl_interval_minutes": 60,
        "reliability_score": 92,
    },
    {
        "name": "Epoch AI 最新研究",
        "url": "https://epoch.ai/latest",
        "source_type": "web_page_list",
        "tier": "T1",
        "language": "en",
        "category_hint": "论文研究",
        "crawl_interval_minutes": 240,
        "reliability_score": 91,
        "extra": {
            "link_prefixes": [
                "/blog/",
                "/gradient-updates/",
                "/data-insights/",
                "/epoch-after-hours/",
            ],
            "max_items": 24,
        },
    },
    {
        "name": "CMU School of Computer Science News",
        "url": "https://www.cs.cmu.edu/news",
        "source_type": "web_page_list",
        "tier": "T1_5",
        "language": "en",
        "category_hint": "论文研究",
        "crawl_interval_minutes": 240,
        "reliability_score": 84,
        "extra": {
            "link_prefixes": ["/news/"],
            "max_items": 15,
        },
    },
    {
        "name": "Simon Willison",
        "url": "https://simonwillison.net/atom/everything/",
        "source_type": "rss",
        "tier": "T2",
        "language": "en",
        "category_hint": "技巧与观点",
        "crawl_interval_minutes": 60,
        "reliability_score": 88,
    },
    {
        "name": "Hacker News AI",
        "url": "https://hnrss.org/newest?q=AI",
        "source_type": "rss",
        "tier": "T2",
        "language": "en",
        "category_hint": "行业动态",
        "crawl_interval_minutes": 30,
        "reliability_score": 78,
    },
    {
        "name": "GitHub AI 热门仓库",
        "url": "https://api.github.com/search/repositories?q=topic:artificial-intelligence+stars:%3E1000+forks:%3E50+archived:false&sort=stars&order=desc",
        "source_type": "github_trending",
        "tier": "T1_5",
        "language": "en",
        "category_hint": "产品发布/更新",
        "crawl_interval_minutes": 180,
        "reliability_score": 88,
        "extra": {
            "queries": [
                "topic:artificial-intelligence stars:>1000 forks:>50 archived:false",
                "topic:llm stars:>500 forks:>30 archived:false",
                "topic:ai-agents stars:>300 forks:>20 archived:false",
                "topic:rag stars:>300 forks:>20 archived:false",
            ],
            "per_page": 10,
            "sort": "stars",
        },
    },
    {
        "name": "GitHub 官方 Trending",
        "url": "https://github.com/trending?since=daily&spoken_language_code=en",
        "source_type": "github_trending_page",
        "tier": "T1_5",
        "language": "en",
        "category_hint": "产品发布/更新",
        "crawl_interval_minutes": 120,
        "reliability_score": 90,
        "extra": {
            "urls": [
                "https://github.com/trending?since=daily&spoken_language_code=en",
                "https://github.com/trending?since=weekly&spoken_language_code=en",
            ],
            "max_repos": 30,
        },
    },
    {
        "name": "GitHub AI 官方 Topic",
        "url": "https://github.com/topics/artificial-intelligence",
        "source_type": "github_topic_page",
        "tier": "T1_5",
        "language": "en",
        "category_hint": "产品发布/更新",
        "crawl_interval_minutes": 240,
        "reliability_score": 84,
        "extra": {
            "urls": [
                "https://github.com/topics/artificial-intelligence",
                "https://github.com/topics/llm",
                "https://github.com/topics/ai-agents",
                "https://github.com/topics/rag",
            ],
            "max_repos": 20,
        },
    },
    {
        "name": "X AI 热议",
        "url": "https://api.twitter.com/2/tweets/search/recent?query=(AI%20OR%20LLM%20OR%20OpenAI%20OR%20agent)%20-is:retweet%20lang:en",
        "source_type": "x_recent_search",
        "tier": "T2",
        "language": "en",
        "category_hint": "行业动态",
        "crawl_interval_minutes": 30,
        "is_enabled": False,
        "reliability_score": 70,
        "extra": {
            "query": "(AI OR LLM OR OpenAI OR agent) -is:retweet lang:en",
            "note": "需要配置 X_BEARER_TOKEN 后启用。",
        },
    },
]


async def seed_sources(db: AsyncSession) -> int:
    legacy = (
        await db.execute(
            select(Source).where(Source.name.in_(["GitHub AI 趋势", "GitHub AI 趋势（旧规则停用）"]))
        )
    ).scalars().all()
    for source in legacy:
        await db.delete(source)
    created = 0
    for payload in SEED_SOURCES:
        existing = await db.execute(select(Source).where(Source.url == payload["url"]))
        source = existing.scalar_one_or_none()
        if source:
            if source.source_type == "x_recent_search" and get_settings().x_bearer_token:
                source.is_enabled = True
            continue
        db.add(Source(**payload))
        created += 1
    if created or legacy:
        await db.commit()
    return created
