from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin
from uuid import UUID

import httpx
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.item import Item
from app.models.raw_item import RawItem
from app.models.source import Source
from app.models.wechat_draft import WechatDraft
from app.services.llm import BigModelClient
from app.services.wechat_client import WechatApiError, WechatClient


GITHUB_WECHAT_STYLE = {
    "structure": [
        "开场用一句话说明项目解决了什么问题",
        "标题直接说明项目用途和优势",
        "开场说明项目解决的问题，不写趋势信号",
        "基于 README 总结功能亮点、技术路线和适用场景",
        "提供 README 中的安装命令、示例代码或最小使用路径",
        "明确限制、风险和同类项目对比视角",
        "结尾给出项目链接和读者行动建议",
    ],
    "images": [
        "封面优先用 GitHub 仓库主页 OpenGraph 图或主页截图",
        "正文优先使用 README 中的架构图、界面截图或 demo 图，前提是 license 允许转载",
        "自绘流程图：输入、核心模块、输出、适用场景",
        "表格图：功能、适合人群、上手成本、风险点",
    ],
    "tone": [
        "标题有信息密度，但避免夸大为神器、颠覆、必火",
        "正文口吻适合技术读者，少堆形容词，多引用 README 证据",
        "不要把 GitHub stars、forks、trending rank 写成正文卖点",
        "如果没有实际试用，只能写代码阅读和 README 级判断",
    ],
}


def is_github_source(source: Source) -> bool:
    return source.source_type.startswith("github")


async def choose_github_item(db: AsyncSession, item_id: str | None = None) -> tuple[Item, RawItem, Source]:
    stmt = (
        select(Item, RawItem, Source)
        .join(RawItem, RawItem.id == Item.raw_id)
        .join(Source, Source.id == Item.source_id)
    )
    if item_id:
        try:
            UUID(item_id)
        except ValueError as exc:
            raise ValueError("item_id 必须是有效 UUID") from exc
        stmt = stmt.where(Item.id == item_id)
    else:
        stmt = stmt.where(Source.source_type.like("github%"), Item.is_ai_related.is_(True)).order_by(
            desc(Item.final_score), desc(Item.published_at).nullslast(), desc(Item.created_at)
        )
    row = (await db.execute(stmt.limit(1))).first()
    if not row:
        raise ValueError("未找到可生成公众号稿的 GitHub 项目")
    item, raw, source = row
    if not is_github_source(source):
        raise ValueError("所选条目不是 GitHub 项目")
    return item, raw, source


def repo_name(item: Item) -> str:
    title = item.title_original.split(":", 1)[0].strip()
    if "/" in title:
        return title
    return item.canonical_url.rstrip("/").replace("https://github.com/", "")


def repo_metrics(raw: RawItem) -> dict[str, Any]:
    extra = raw.extra or {}
    return {
        "stars": int(extra.get("stars") or 0),
        "forks": int(extra.get("forks") or 0),
        "stars_today": int(extra.get("stars_today") or 0),
        "trending_rank": extra.get("trending_rank"),
        "language": extra.get("language") or "unknown",
        "topics": extra.get("topics") or [],
        "discovery_url": extra.get("discovery_url"),
    }


def repo_slug(item: Item) -> str:
    return repo_name(item).replace("https://github.com/", "").strip("/")


def github_og_image(item: Item) -> str:
    return f"https://opengraph.githubassets.com/aiinfo/{repo_slug(item)}"


def project_description(item: Item, raw: RawItem) -> str:
    if ":" in item.title_original:
        desc = item.title_original.split(":", 1)[1].strip()
        if desc:
            return desc[:260]
    text = raw.raw_content or item.content_text or item.summary_short
    text = re.sub(r"GitHub\s*仓库趋势信号。?", "", text)
    text = re.sub(r"stars:\s*\d+;?", "", text, flags=re.I)
    text = re.sub(r"forks:\s*\d+;?", "", text, flags=re.I)
    text = re.sub(r"stars today:\s*\d+;?", "", text, flags=re.I)
    text = re.sub(r"language:\s*[^;.]+[;.]?", "", text, flags=re.I)
    text = re.sub(r"topics:\s*[^.]+[.]?", "", text, flags=re.I)
    return text.strip(" ;.。")[:260] or "这个项目提供了一套面向 AI 开发场景的开源能力。"


def fallback_title(item: Item, raw: RawItem) -> str:
    name = repo_name(item).split("/")[-1]
    desc = project_description(item, raw)
    if "design" in name.lower() or "设计" in desc:
        return f"{name}：本地优先的 AI 设计工具"
    if "agent" in desc.lower() or "agent" in name.lower():
        return f"{name}：面向开发者的 AI Agent 工具"
    if "workflow" in desc.lower():
        return f"{name}：简化 AI 工作流的开源工具"
    return f"{name}：快速上手的 AI 开源工具"


def extract_markdown_images(markdown: str, base_url: str) -> list[str]:
    urls: list[str] = []
    for pattern in (r"!\[[^\]]*\]\(([^)]+)\)", r"<img[^>]+src=[\"']([^\"']+)[\"']"):
        for match in re.finditer(pattern, markdown, flags=re.I):
            url = match.group(1).strip()
            if url.startswith("#") or url.startswith("data:"):
                continue
            absolute = urljoin(base_url, url)
            if absolute.startswith(("http://", "https://")) and absolute not in urls:
                urls.append(absolute)
            if len(urls) >= 3:
                return urls
    return urls


def readme_sections(markdown: str) -> str:
    lines: list[str] = []
    in_code = False
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            lines.append(line)
            continue
        if in_code or stripped.startswith(("#", "-", "*", "1.", "2.", "3.", "4.", "5.")):
            lines.append(line)
        elif stripped and len(stripped) > 30:
            lines.append(line)
        if len("\n".join(lines)) > 4000:
            break
    return "\n".join(lines)[:4000]


def readme_code_examples(markdown: str) -> list[str]:
    examples: list[str] = []
    for match in re.finditer(r"```[^\n]*\n(.*?)```", markdown, flags=re.S):
        code = match.group(1).strip()
        if 10 <= len(code) <= 500:
            examples.append(code)
        if len(examples) >= 2:
            break
    return examples


def readme_bullets(markdown: str) -> list[str]:
    bullets: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")) and len(stripped) > 12:
            text = re.sub(r"[*_`#]", "", stripped[2:]).strip()
            if text and text not in bullets:
                bullets.append(text[:160])
        if len(bullets) >= 5:
            break
    return bullets


async def fetch_github_readme(item: Item) -> dict[str, Any]:
    slug = repo_slug(item)
    headers = github_headers()
    async with httpx.AsyncClient(timeout=25, follow_redirects=True, trust_env=False) as client:
        response = await client.get(f"https://api.github.com/repos/{slug}/readme", headers=headers)
        response.raise_for_status()
        payload = response.json()
        download_url = payload.get("download_url")
        if not download_url:
            return {"markdown": "", "images": []}
        readme_response = await client.get(download_url, headers={"User-Agent": "AIIntelRadarBot/0.1 (+local-dev)"})
        readme_response.raise_for_status()
        markdown = readme_response.text
    return {
        "markdown": markdown,
        "summary": readme_sections(markdown),
        "images": extract_markdown_images(markdown, download_url),
        "download_url": download_url,
    }


def fallback_article(item: Item, raw: RawItem, readme: dict[str, Any] | None = None) -> dict[str, Any]:
    name = repo_name(item)
    metrics = repo_metrics(raw)
    topics = "、".join(metrics["topics"][:6]) if metrics["topics"] else "暂未标注"
    desc = project_description(item, raw)
    title = fallback_title(item, raw)
    digest = f"{name} 的 README 显示，它可以从解决的问题、核心能力、上手路径和适用场景四个角度快速评估。"
    readme_markdown = str((readme or {}).get("markdown") or "")
    bullets = readme_bullets(readme_markdown)
    examples = readme_code_examples(readme_markdown)
    bullet_text = "\n".join(f"- **README 要点**：{text}" for text in bullets[:4]) or (
        "- **README 要点**：先看安装方式、示例命令、配置说明和导出能力。"
    )
    example_text = "\n\n".join(f"```bash\n{example}\n```" for example in examples[:2]) or (
        "如果 README 提供安装命令或 demo，建议先跑通最小示例，再判断是否适合自己的项目。"
    )
    markdown = f"""# {title}

## 这个项目解决什么问题

**{desc}**

## 它的主要优势

- **定位清晰**：围绕 README 描述中的具体使用场景展开，而不是只靠热度判断。
- **技术栈明确**：主要语言是 **{metrics["language"]}**，主题包括 {topics}。
- **适合快速评估**：可以先从 README 的安装命令、示例代码和 demo 图判断上手成本。

## README 里的关键内容

{bullet_text}

## README 示例展示

{example_text}

## 适合谁使用

- **开发者**：用它作为 AI 工程样例或工具链补充。
- **产品和技术负责人**：用它判断某类 AI 工具是否已有开源实现。
- **内容创作者**：用 README 截图、示例命令和功能图做图文拆解。

## 使用前要确认

**不要只看热度。** 正式采用前，建议确认 license、最近提交、issue 回复、README 示例是否能跑通。

## 项目地址

{item.canonical_url}
"""
    return {
        "title": title,
        "digest": digest,
        "markdown": markdown,
        "image_plan": {
            "items": [
                {"type": "github_homepage", "source": item.canonical_url, "note": "仓库首页截图，需遮挡无关浏览器信息"},
                {"type": "readme_asset", "source": item.canonical_url, "note": "优先选 README 中明确许可可转载的图"},
                {"type": "self_made_diagram", "source": "editorial", "note": "自绘流程图，降低版权风险"},
            ]
        },
        "style_notes": GITHUB_WECHAT_STYLE,
    }


def writer_prompt(item: Item, raw: RawItem, source: Source, readme: dict[str, Any]) -> list[dict[str, str]]:
    metrics = repo_metrics(raw)
    return [
        {
            "role": "system",
            "content": (
                "你是中文技术公众号编辑，专门写 GitHub AI 开源项目解读。"
                "输出必须是 JSON object，字段为 title, digest, markdown, image_plan, style_notes。"
                "不要夸大项目，不要声称已经生产可用，除非证据明确。"
                "不要在正文写 GitHub stars、forks、trending rank 等趋势信号。"
                "标题要说清楚项目用途和优势，不要写“值得关注”。"
                "正文关键短语用 **加粗**。"
                "除项目名、命令和专有名词外，正文必须用中文写作。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请基于以下 GitHub 项目信息写一篇公众号草稿，并生成配图计划。\n"
                f"项目名: {repo_name(item)}\n"
                f"链接: {item.canonical_url}\n"
                f"来源: {source.name} / {source.source_type}\n"
                f"标题: {item.title_original}\n"
                f"摘要: {item.summary_short}\n"
                f"采集线索: {item.content_text[:1000]}\n"
                f"README 摘要和示例: {readme.get('summary', '')}\n"
                f"内部参考指标（只用于判断，不要写进正文）: {metrics}\n"
                f"可用 README 图片: {readme.get('images', [])}\n"
                f"写作方法参考: {GITHUB_WECHAT_STYLE}\n"
                "要求：标题不要超过 28 个中文字符；digest 不超过 120 字；"
                "markdown 包含：项目解决什么问题、核心优势、README 示例/命令、适用场景、使用前注意、项目地址。"
                "不要写“GitHub 趋势信号”“stars”“forks”“今日新增 stars”等表达。"
            ),
        },
    ]


def normalize_article(
    payload: dict[str, Any], item: Item, raw: RawItem, readme: dict[str, Any] | None = None
) -> dict[str, Any]:
    fallback = fallback_article(item, raw, readme)
    title = str(payload.get("title") or fallback["title"]).strip()
    digest = str(payload.get("digest") or fallback["digest"]).strip()
    markdown = str(payload.get("markdown") or fallback["markdown"]).strip()
    if readme and "示例" not in markdown:
        examples = readme_code_examples(str(readme.get("markdown") or ""))
        example_text = "\n\n".join(f"```bash\n{example}\n```" for example in examples[:2])
        if example_text:
            markdown = f"{markdown}\n\n## README 示例展示\n\n{example_text}"
    image_plan = payload.get("image_plan") if isinstance(payload.get("image_plan"), dict) else fallback["image_plan"]
    style_notes = payload.get("style_notes") if isinstance(payload.get("style_notes"), dict) else fallback["style_notes"]
    return {
        "title": title[:120],
        "digest": digest[:300],
        "markdown": markdown,
        "image_plan": image_plan,
        "style_notes": style_notes,
    }


async def generate_github_wechat_draft(
    db: AsyncSession,
    *,
    item_id: str | None = None,
    submit: bool = True,
) -> WechatDraft:
    item, raw, source = await choose_github_item(db, item_id)
    try:
        readme = await fetch_github_readme(item)
    except Exception:
        readme = {"markdown": "", "summary": "", "images": []}
    article = fallback_article(item, raw, readme)
    generation_error = None
    try:
        client = BigModelClient()
        payload, _usage = await client.chat_json(
            model=client.settings.llm_model_summary,
            messages=writer_prompt(item, raw, source, readme),
            temperature=client.settings.llm_temperature_summary,
            max_tokens=min(client.settings.llm_max_tokens_summary, 3500),
        )
        article = normalize_article(payload, item, raw, readme)
    except Exception as exc:
        generation_error = str(exc)

    settings = get_settings()
    if submit and settings.wechat_draft_enabled and settings.wechat_app_id and settings.wechat_app_secret:
        try:
            wechat_result = await WechatClient().add_draft(
                title=article["title"],
                digest=article["digest"],
                markdown=article["markdown"],
                content_source_url=settings.wechat_source_url or item.canonical_url,
                cover_image_url=github_og_image(item),
                body_image_urls=readme.get("images", []),
            )
            submission_status = "submitted_to_wechat_draft"
            submit_result = {
                "message": "已提交到微信公众号草稿箱。",
                "media_id": wechat_result.get("media_id"),
                "thumb_media_id": wechat_result.get("thumb_media_id"),
                "uploaded_images": wechat_result.get("uploaded_images", []),
            }
        except (WechatApiError, httpx.HTTPError, ValueError) as exc:
            submission_status = "wechat_submit_failed"
            submit_result = {
                "message": f"微信草稿箱提交失败：{exc}",
            }
    elif submit:
        submission_status = "saved_pending_wechat_credentials"
        submit_result = {
            "message": "已生成并保存草稿；未配置微信凭据或 WECHAT_DRAFT_ENABLED=false，未上传微信草稿箱。",
        }
    else:
        submission_status = "drafted"
        submit_result = {"message": "仅生成草稿，未请求提交。"}
    if generation_error:
        submit_result["generation_fallback"] = generation_error

    draft = WechatDraft(
        item_id=item.id,
        draft_type="github_project",
        title=article["title"],
        digest=article["digest"],
        markdown=article["markdown"],
        image_plan=article["image_plan"],
        style_notes=article["style_notes"],
        submission_status=submission_status,
        submit_result=submit_result,
    )
    db.add(draft)
    await db.commit()
    await db.refresh(draft)
    return draft
