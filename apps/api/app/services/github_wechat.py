from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.item import Item
from app.models.raw_item import RawItem
from app.models.source import Source
from app.models.wechat_draft import WechatDraft
from app.services.llm import BigModelClient


GITHUB_WECHAT_STYLE = {
    "structure": [
        "开场用一句话说明项目解决了什么问题",
        "给出 GitHub 热度信号和为什么现在值得看",
        "用三到五个小节拆解功能亮点、技术路线和适用场景",
        "提供快速上手命令或最小使用路径",
        "明确限制、风险和同类项目对比视角",
        "结尾给出项目链接和读者行动建议",
    ],
    "images": [
        "GitHub 仓库首页或 social preview，展示项目名称、stars、forks 和 README 首屏",
        "README 中的架构图、界面截图或 demo 图，前提是 license 允许转载",
        "自绘流程图：输入、核心模块、输出、适用场景",
        "表格图：功能、适合人群、上手成本、风险点",
    ],
    "tone": [
        "标题有信息密度，但避免夸大为神器、颠覆、必火",
        "正文口吻适合技术读者，少堆形容词，多给判断依据",
        "对 star 数、更新频率、license、维护状态保持审慎",
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


def fallback_article(item: Item, raw: RawItem) -> dict[str, Any]:
    name = repo_name(item)
    metrics = repo_metrics(raw)
    topics = "、".join(metrics["topics"][:6]) if metrics["topics"] else "暂未标注"
    title = f"{name}：一个值得关注的 AI 开源项目"
    digest = f"{name} 在 GitHub 上表现活跃，适合从用途、技术路线、上手成本和维护信号四个角度判断是否值得跟进。"
    markdown = f"""# {title}

## 一句话看懂

{item.summary_short or raw.raw_content}

## 为什么现在值得看

- GitHub stars：{metrics["stars"]}
- forks：{metrics["forks"]}
- 今日新增 stars：{metrics["stars_today"]}
- 主要语言：{metrics["language"]}
- 主题标签：{topics}
- 项目链接：{item.canonical_url}

这些指标不能直接证明项目质量，但能说明它正在被开发者关注。对公众号读者来说，更重要的是它解决什么问题、是否容易上手、维护是否稳定。

## 它可能解决的问题

从仓库描述看，这个项目与 AI 开发、工程效率或应用构建有关。写作时建议把它放进一个具体场景：例如本地开发、智能体工作流、RAG 应用、模型部署、数据处理或前端交互。

## 值得展开的功能点

1. 项目定位：它面向开发者、研究者还是产品团队。
2. 技术路线：核心模块、依赖栈、输入输出路径。
3. 上手体验：README 是否有安装命令、示例代码和 demo。
4. 维护信号：stars、forks、近期提交、issue 活跃度。
5. 风险限制：license、文档完整性、生产可用性和同类替代。

## 推荐配图

1. GitHub 仓库首页截图，展示项目名、stars、forks 和 README 首屏。
2. README 中的架构图或界面截图；转载前检查 license。
3. 自绘一张“输入 - 核心模块 - 输出 - 使用场景”的流程图。
4. 自制表格：功能亮点、适合人群、上手成本、风险点。

## 适合谁关注

- 想快速筛选 AI 开源项目的开发者。
- 需要找工程样例或技术选型参考的团队。
- 希望跟踪 GitHub AI 趋势的产品和研究人员。

## 先别过度解读

GitHub 热度不是质量保证。正式推荐前，建议至少检查 README、license、最近提交、issue 回复情况，并实际跑通最小示例。

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


def writer_prompt(item: Item, raw: RawItem, source: Source) -> list[dict[str, str]]:
    metrics = repo_metrics(raw)
    return [
        {
            "role": "system",
            "content": (
                "你是中文技术公众号编辑，专门写 GitHub AI 开源项目解读。"
                "输出必须是 JSON object，字段为 title, digest, markdown, image_plan, style_notes。"
                "不要夸大项目，不要声称已经生产可用，除非证据明确。"
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
                f"正文线索: {item.content_text[:1800]}\n"
                f"热度指标: {metrics}\n"
                f"写作方法参考: {GITHUB_WECHAT_STYLE}\n"
                "要求：标题不要超过 28 个中文字符；digest 不超过 120 字；"
                "markdown 包含：开场、为什么值得看、核心功能、快速上手、配图建议、限制、项目地址。"
            ),
        },
    ]


def normalize_article(payload: dict[str, Any], item: Item, raw: RawItem) -> dict[str, Any]:
    fallback = fallback_article(item, raw)
    title = str(payload.get("title") or fallback["title"]).strip()
    digest = str(payload.get("digest") or fallback["digest"]).strip()
    markdown = str(payload.get("markdown") or fallback["markdown"]).strip()
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
    article = fallback_article(item, raw)
    generation_error = None
    try:
        client = BigModelClient()
        payload, _usage = await client.chat_json(
            model=client.settings.llm_model_summary,
            messages=writer_prompt(item, raw, source),
            temperature=client.settings.llm_temperature_summary,
            max_tokens=min(client.settings.llm_max_tokens_summary, 3500),
        )
        article = normalize_article(payload, item, raw)
    except Exception as exc:
        generation_error = str(exc)

    settings = get_settings()
    if submit and settings.wechat_app_id and settings.wechat_app_secret:
        submission_status = "ready_for_wechat_upload"
        submit_result = {
            "message": "已生成公众号草稿。当前版本未直接调用微信草稿箱 API，请接入上传预览后再发布。",
            "requires": ["cover image", "image upload", "preview check", "draft-box API"],
        }
    elif submit:
        submission_status = "saved_pending_wechat_credentials"
        submit_result = {
            "message": "已生成并保存草稿；未配置 WECHAT_APP_ID/WECHAT_APP_SECRET，未上传微信草稿箱。",
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
