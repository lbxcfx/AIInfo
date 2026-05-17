from datetime import datetime, timezone

from app.models.item import Item
from app.models.raw_item import RawItem
from app.services.github_wechat import (
    article_quality_issue,
    fallback_article,
    insert_before_project_address,
    normalize_installation_and_project_address,
    normalize_image_plan,
    normalize_wechat_markdown,
    repo_metrics,
    repo_name,
)
from app.services.wechat_client import insert_uploaded_images, markdown_to_wechat_html


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
    assert "AI" in article["title"]
    assert "## 这个项目解决什么问题" in article["markdown"]
    assert "## README 功能拆解" in article["markdown"]
    assert "## 安装方法" in article["markdown"]
    assert "GitHub stars" not in article["markdown"]
    image_types = {item["type"] for item in article["image_plan"]["items"]}
    assert {"cover", "github_homepage", "readme_asset", "repo_screenshot_fallback"} <= image_types
    assert "metrics_card" not in image_types
    assert "self_made_diagram" not in image_types
    assert all({"type", "source", "placement", "caption", "note"} <= set(item) for item in article["image_plan"]["items"])


def test_normalize_image_plan_backfills_required_slots() -> None:
    plan = normalize_image_plan(
        {"items": [{"type": "readme_asset", "source": "https://example.com/demo.png"}]},
        make_item(),
    )
    by_type = {item["type"]: item for item in plan["items"]}
    assert by_type["readme_asset"]["source"] == "https://example.com/demo.png"
    assert {"cover", "github_homepage", "readme_asset", "repo_screenshot_fallback"} <= set(by_type)
    assert all(item["caption"] for item in plan["items"])


def test_wechat_html_removes_h1_and_keeps_sections() -> None:
    html = markdown_to_wechat_html("# Title\n\n## Section\n\n- item\n\nProject: https://github.com/example/ai-tool")
    assert "<h1" not in html
    assert ">Section</h2>" in html
    assert ">item</li>" in html


def test_normalize_wechat_markdown_adds_single_h1_and_repairs_code_block() -> None:
    markdown = "痛点开场\n\n### 最小上手路径\n\nbash\nnpm install -g demo\n\n项目地址：https://github.com/example/demo"
    normalized = normalize_wechat_markdown("Demo：AI 工具", markdown)
    assert normalized.startswith("# Demo：AI 工具")
    assert normalized.count("\n# ") == 0
    assert "## 最小上手路径" in normalized
    assert "```bash\nnpm install -g demo\n```" in normalized


def test_normalize_wechat_markdown_demotes_extra_h1() -> None:
    normalized = normalize_wechat_markdown("主标题", "# 旧标题\n\n# 误用标题\n\n正文")
    assert normalized.splitlines()[0] == "# 主标题"
    assert "## 误用标题" in normalized
    assert normalized.count("\n# ") == 0


def test_article_quality_issue_rejects_truncated_article() -> None:
    issue = article_quality_issue("# 标题\n\n## 解决什么问题\n\n这是一个基于")
    assert issue == "正文过短，疑似生成截断"


def test_insert_before_project_address_keeps_examples_before_link() -> None:
    markdown = "# 标题\n\n## 正文\n内容\n\n## 项目地址\nhttps://github.com/example/demo"
    updated = insert_before_project_address(markdown, "## README 示例展示\n\n```bash\npnpm demo\n```")
    assert updated.index("## README 示例展示") < updated.index("## 项目地址")


def test_markdown_to_wechat_html_renders_scrollable_code() -> None:
    html = markdown_to_wechat_html("# Title\n\n## 安装方法\n\n```bash\npip install demo-package --with-a-very-long-option\n```")
    assert "overflow-x:auto" in html
    assert "左右滑动查看完整命令" in html
    assert "<pre" in html


def test_normalize_project_address_heading_and_installation_order() -> None:
    markdown = "# 标题\n\n## 项目地址与下一步建议\n项目地址：https://github.com/example/demo\n\n## README 示例展示\n```bash\npip install demo\n```"
    normalized = normalize_installation_and_project_address(markdown)
    assert "项目地址与下一步建议" not in normalized
    assert "## 安装方法" in normalized
    assert normalized.index("## 安装方法") < normalized.index("## 项目地址")
    assert "项目地址：https" not in normalized
    assert "## 项目地址\n\nhttps://github.com/example/demo" in normalized
    assert normalized.count("## 项目地址") == 1


def test_insert_uploaded_images_places_figures_near_relevant_sections() -> None:
    markdown = "# 标题\n\n## 痛点：先看问题\n正文一\n\n## 核心能力\n正文二\n\n## 项目地址\nhttps://github.com/example/demo"
    updated = insert_uploaded_images(markdown, ["https://mmbiz.qpic.cn/a.png", "https://mmbiz.qpic.cn/b.png"])
    assert updated.index("图 1｜仓库原生配图") > updated.index("## 痛点")
    assert updated.index("图 1｜仓库原生配图") < updated.index("## 核心能力")
    assert updated.index("图 2｜仓库原生配图") > updated.index("## 核心能力")
    assert updated.index("图 2｜仓库原生配图") < updated.index("## 项目地址")


def test_markdown_to_wechat_html_omits_visible_image_caption() -> None:
    html = markdown_to_wechat_html("![图 1｜项目速览](https://mmbiz.qpic.cn/a.png)")
    assert "图 1｜项目速览" in html
    assert ">图 1｜项目速览</p>" not in html
    assert "text-align:center" in html


def test_markdown_to_wechat_html_renders_video_link_not_iframe() -> None:
    html = markdown_to_wechat_html("@video_link(https://github.com/user-attachments/assets/demo, 查看 GitHub 原生演示视频)")
    assert "video_iframe" not in html
    assert "https://github.com/user-attachments/assets/demo" in html
    assert "查看 GitHub 原生演示视频" in html
