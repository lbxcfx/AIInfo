from datetime import datetime, timezone

from app.models.item import Item
from app.models.raw_item import RawItem
from app.services.github_wechat import fallback_article, repo_metrics, repo_name
from app.services.wechat_client import markdown_to_wechat_html


def make_item() -> Item:
    return Item(
        id="item-1",
        raw_id="raw-1",
        source_id="source-1",
        canonical_url="https://github.com/example/ai-tool",
        title_original="example/ai-tool: AI workflow helper",
        content_text="GitHub 仓库趋势信号。stars: 1200; forks: 180; language: Python.",
        summary_short="A helper for AI workflows.",
        language="en",
        category="产品发布/更新",
        entities={},
        published_at=datetime.now(timezone.utc),
        is_ai_related=True,
        relevance_score=0.9,
        final_score=88,
        is_featured=True,
    )


def make_raw() -> RawItem:
    return RawItem(
        id="raw-1",
        source_id="source-1",
        raw_url="https://github.com/example/ai-tool",
        fetched_url="https://github.com/trending",
        raw_title="example/ai-tool: AI workflow helper",
        raw_content="GitHub 仓库趋势信号。",
        http_status=200,
        content_hash="hash",
        fetch_status="ok",
        extra={
            "stars": 1200,
            "forks": 180,
            "stars_today": 42,
            "language": "Python",
            "topics": ["ai", "agents", "workflow"],
        },
    )


def test_repo_name_prefers_owner_repo_prefix() -> None:
    assert repo_name(make_item()) == "example/ai-tool"


def test_repo_metrics_normalizes_extra_values() -> None:
    metrics = repo_metrics(make_raw())
    assert metrics["stars"] == 1200
    assert metrics["forks"] == 180
    assert metrics["language"] == "Python"
    assert metrics["topics"] == ["ai", "agents", "workflow"]


def test_fallback_article_has_wechat_sections() -> None:
    article = fallback_article(make_item(), make_raw())
    assert "example/ai-tool" in article["title"]
    assert "## 为什么现在值得看" in article["markdown"]
    assert "## 推荐配图" in article["markdown"]
    assert article["image_plan"]["items"]


def test_wechat_html_removes_h1_and_keeps_sections() -> None:
    html = markdown_to_wechat_html("# Title\n\n## Section\n\n- item\n\nProject: https://github.com/example/ai-tool")
    assert "<h1" not in html
    assert "<h2>Section</h2>" in html
    assert "<li>item</li>" in html
