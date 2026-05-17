from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
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
        "标题直接说明项目用途、读者收益和差异点",
        "开场先写具体痛点，再说明项目用什么方式解决",
        "正文按问题、功能、上手、场景、风险、行动建议展开",
        "基于 README 总结功能亮点、技术路线、输入输出和适用场景",
        "提供 README 中的安装命令、示例代码、demo 路径或最小使用路径",
        "用 README 中的 demo 图、截图、架构图或自绘图解释能力，不只做文字概括",
        "明确 license、维护活跃度、文档完整度、生产稳定性和同类替代项目",
        "结尾给出项目链接，并告诉读者下一步应该 Star、试跑 demo 还是继续观察",
    ],
    "images": [
        "封面优先用 GitHub OpenGraph 图或仓库主页截图",
        "正文优先使用 README 中原生存在的 demo 图、界面截图、架构图或视频封面",
        "如果 README 没有有效图片，再使用仓库页面截图或 GitHub 原生预览图兜底",
        "不要为项目正文 AI 生成概念图、指标卡或工作流图",
    ],
    "tone": [
        "标题有信息密度，但避免夸大为神器、颠覆、必火",
        "开头先写痛点，再说明项目如何降低成本、提升效果或缩短试错路径",
        "正文口吻适合技术读者，少堆空泛形容词，多引用 README 里的功能、示例和限制",
        "不要把 GitHub stars、forks、trending rank 写成正文卖点",
        "如果没有实际试用，只能写代码阅读和 README 级判断",
        "每个功能点都要回答：它是什么、解决什么问题、读者如何验证",
    ],
}

README_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
LOW_VALUE_IMAGE_HINTS = (
    "badge",
    "shields.io",
    "license",
    "ci",
    "build",
    "coverage",
    "discord",
    "twitter",
    "x.com",
    "logo",
    "sponsor",
    "sponsors",
)
HIGH_VALUE_IMAGE_HINTS = (
    "demo",
    "example",
    "examples",
    "screenshot",
    "screen",
    "preview",
    "showcase",
    "assets",
    "docs",
    "media",
    "image",
    "workflow",
)


def github_headers() -> dict[str, str]:
    settings = get_settings()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AIIntelRadarBot/0.1 (+local-dev)",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


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


def default_image_plan(item: Item) -> dict[str, Any]:
    name = repo_name(item)
    return {
        "items": [
            {
                "type": "cover",
                "source": github_og_image(item),
                "placement": "cover",
                "caption": f"{name}：用一张图说明项目定位和核心价值",
                "note": "优先作为封面；发布前检查项目名、标题叠字和版权风险。",
            },
            {
                "type": "github_homepage",
                "source": item.canonical_url,
                "placement": "正文开场后",
                "caption": "仓库首页截图：项目名、README 首屏和基础信息放在同一屏。",
                "note": "用于建立读者的第一印象；截图时避免暴露浏览器隐私信息。",
            },
            {
                "type": "readme_asset",
                "source": item.canonical_url,
                "placement": "README 功能拆解中",
                "caption": "README demo 或架构图：优先展示输入、处理过程和输出结果。",
                "note": "只使用 license 明确允许转载的图片；不确定时改为自绘图。",
            },
            {
                "type": "repo_screenshot_fallback",
                "source": item.canonical_url,
                "placement": "痛点开场后",
                "caption": "仓库页面截图：当 README 没有可用图片时，用仓库首屏补足视觉信息。",
                "note": "优先真实网页截图；当前无截图工具时使用 GitHub 原生预览图兜底。",
            },
        ]
    }


def normalize_image_plan(payload: Any, item: Item) -> dict[str, Any]:
    defaults = default_image_plan(item)
    if not isinstance(payload, dict):
        return defaults

    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return defaults

    defaults_by_type = {entry["type"]: entry for entry in defaults["items"]}
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        image_type = str(raw.get("type") or "").strip()
        if not image_type:
            continue
        base = defaults_by_type.get(image_type, {})
        entry = {
            "type": image_type,
            "source": str(raw.get("source") or base.get("source") or "editorial"),
            "placement": str(raw.get("placement") or base.get("placement") or "正文中"),
            "caption": str(raw.get("caption") or base.get("caption") or "配图说明待补充"),
            "note": str(raw.get("note") or base.get("note") or "发布前人工复核。"),
        }
        normalized.append(entry)
        seen.add(image_type)

    for default in defaults["items"]:
        if default["type"] not in seen:
            normalized.append(default)

    return {"items": normalized}


CODE_BLOCK_LANGUAGES = {"bash", "sh", "shell", "python", "json", "yaml", "toml", "typescript", "javascript"}
COMMAND_PREFIXES = ("npm ", "pnpm ", "yarn ", "pip ", "uv ", "git ", "curl ", "python ", "docker ", "npx ", "$ ")


def _looks_like_code_line(value: str) -> bool:
    stripped = value.strip()
    return stripped.startswith(COMMAND_PREFIXES) or stripped.startswith(("{", "["))


def repair_orphan_code_blocks(markdown: str) -> str:
    lines = markdown.splitlines()
    repaired: list[str] = []
    index = 0
    in_fence = False
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            repaired.append(line)
            index += 1
            continue
        if (
            not in_fence
            and stripped.lower() in CODE_BLOCK_LANGUAGES
            and index + 1 < len(lines)
            and _looks_like_code_line(lines[index + 1])
        ):
            repaired.append(f"```{stripped.lower()}")
            index += 1
            while index < len(lines) and lines[index].strip():
                repaired.append(lines[index])
                index += 1
            repaired.append("```")
            continue
        repaired.append(line)
        index += 1
    return "\n".join(repaired)


def normalize_wechat_markdown(title: str, markdown: str) -> str:
    cleaned = repair_orphan_code_blocks(markdown.replace("\r\n", "\n").strip())
    if not cleaned:
        return f"# {title}"

    lines = cleaned.splitlines()
    first_content_index = next((index for index, line in enumerate(lines) if line.strip()), 0)
    h1_indexes = [index for index, line in enumerate(lines) if line.startswith("# ")]
    if h1_indexes:
        first_h1 = h1_indexes[0]
        lines[first_h1] = f"# {title}"
        for index in reversed(h1_indexes[1:]):
            lines[index] = "## " + lines[index][2:].strip()
    else:
        lines.insert(first_content_index, f"# {title}")
        lines.insert(first_content_index + 1, "")

    if not any(line.startswith("## ") for line in lines) and any(line.startswith("### ") for line in lines):
        lines = ["## " + line[4:] if line.startswith("### ") else line for line in lines]

    return normalize_installation_and_project_address("\n".join(lines))


REQUIRED_ARTICLE_TERMS = ("解决", "核心", "README", "适合", "使用前", "项目地址")


def article_quality_issue(markdown: str) -> str | None:
    content = markdown.strip()
    if len(content) < 1100:
        return "正文过短，疑似生成截断"
    h1_count = len(re.findall(r"^# ", content, flags=re.M))
    if h1_count != 1:
        return "正文必须包含且只包含一个 H1"
    h2_count = len(re.findall(r"^## ", content, flags=re.M))
    if h2_count < 4:
        return "正文小节不足"
    missing = [term for term in REQUIRED_ARTICLE_TERMS if term not in content]
    if missing:
        return f"正文缺少必要内容：{', '.join(missing)}"
    if re.search(r"(?m)^(bash|python|json|yaml|typescript|javascript)$", content):
        return "正文存在裸代码块语言标记"
    return None


def insert_before_project_address(markdown: str, section: str) -> str:
    marker = "\n## 项目地址"
    if marker in markdown:
        return markdown.replace(marker, f"\n\n{section}{marker}", 1)
    marker = "\n## 项目地址与下一步建议"
    if marker in markdown:
        return markdown.replace(marker, f"\n\n{section}{marker}", 1)
    return f"{markdown}\n\n{section}"


def normalize_installation_and_project_address(markdown: str) -> str:
    content = markdown.replace("## 项目地址与下一步建议", "## 项目地址")
    content = content.replace("## 项目地址和下一步建议", "## 项目地址")
    content = content.replace("## README 示例展示", "## 安装方法")
    content = content.replace("## README 示例/命令", "## 安装方法")
    content = re.sub(r"(?m)^## 项目地址[：:]\s*(https?://\S+)\s*$", r"## 项目地址\n\n\1", content)
    content = re.sub(r"(?m)^项目地址[：:]\s*(https?://\S+)\s*$", r"## 项目地址\n\n\1", content)

    install_match = re.search(r"(?ms)^## 安装方法\n.*?(?=^## |\Z)", content)
    project_match = re.search(r"(?m)^## 项目地址\s*$", content)
    if install_match and project_match and install_match.start() > project_match.start():
        install_block = install_match.group(0).strip()
        content_without_install = content[: install_match.start()] + content[install_match.end() :]
        project_match = re.search(r"(?m)^## 项目地址\s*$", content_without_install)
        if project_match:
            content = content_without_install[: project_match.start()].rstrip() + "\n\n" + install_block + "\n\n" + content_without_install[project_match.start():].lstrip()

    project_blocks = list(re.finditer(r"(?ms)^## 项目地址\n.*?(?=^## |\Z)", content))
    if project_blocks:
        combined = "\n".join(block.group(0) for block in project_blocks)
        url_match = re.search(r"https?://\S+", combined)
        if url_match:
            url = url_match.group(0).rstrip("。.)）]")
            first = project_blocks[0]
            last = project_blocks[-1]
            content = content[: first.start()].rstrip() + f"\n\n## 项目地址\n\n{url}\n\n" + content[last.end():].lstrip()
    return re.sub(r"\n{3,}", "\n\n", content).strip()


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


def is_useful_readme_image(url: str) -> bool:
    parsed = urlparse(url)
    lowered = url.lower()
    suffix = Path(parsed.path).suffix.lower()
    if suffix not in README_IMAGE_SUFFIXES:
        return False
    if any(hint in lowered for hint in LOW_VALUE_IMAGE_HINTS):
        return False
    return True


def readme_image_rank(url: str) -> tuple[int, int]:
    lowered = url.lower()
    score = 0
    for index, hint in enumerate(HIGH_VALUE_IMAGE_HINTS):
        if hint in lowered:
            score += 20 - index
    return (-score, len(url))


def extract_markdown_images(markdown: str, base_url: str) -> list[str]:
    urls: list[str] = []
    patterns = (
        r"!\[[^\]]*\]\(([^)\s]+)(?:\s+[\"'][^\"']+[\"'])?\)",
        r"<img[^>]+src=[\"']([^\"']+)[\"']",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, markdown, flags=re.I):
            url = match.group(1).strip()
            if url.startswith("#") or url.startswith("data:"):
                continue
            absolute = urljoin(base_url, url)
            if absolute.startswith(("http://", "https://")) and absolute not in urls:
                urls.append(absolute)
    return sorted([url for url in urls if is_useful_readme_image(url)], key=readme_image_rank)[:6]


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
    digest = f"{name} 的 README 显示，它适合从问题、功能、上手路径、适用场景和风险五个角度快速评估。"
    readme_markdown = str((readme or {}).get("markdown") or "")
    bullets = readme_bullets(readme_markdown)
    examples = readme_code_examples(readme_markdown)
    bullet_text = "\n".join(f"- **功能线索**：{text}" for text in bullets[:4]) or (
        "- **功能线索**：先看安装方式、示例命令、配置说明、输入输出和导出能力。"
    )
    example_text = "\n\n".join(f"```bash\n{example}\n```" for example in examples[:2]) or (
        "如果 README 提供安装命令或 demo，建议先跑通最小示例，再判断是否适合自己的项目。"
    )
    markdown = f"""# {title}

很多开源项目看起来热闹，但真正值得点开的，往往是那些能把一个具体问题讲清楚、把 demo 和上手路径放到 README 里的项目。**{name}** 的价值，首先在于它把问题收束得比较明确：{desc}

读这类项目不要只看热度，建议先看三件事：**它解决什么问题、README 有没有可复现示例、结果形态是否符合你的工作流**。

## 这个项目解决什么问题

**{desc}**

## 核心功能亮点

- **定位清晰**：围绕 README 描述中的具体使用场景展开，而不是只靠热度判断。
- **技术栈明确**：主要语言是 **{metrics["language"]}**，主题包括 {topics}。
- **适合快速评估**：可以先从 README 的安装命令、示例代码和 demo 图判断上手成本。
- **内容可验证**：如果 README 给出了界面图、流程图或 example，就能更快看出它是不是真的贴近你的工作流。

## README 功能拆解

{bullet_text}

如果你准备把它放进自己的项目里，建议按 **输入、处理过程、输出结果、配置项、扩展方式** 五个维度读 README。这样能更快判断它只是一个 demo，还是已经具备二次开发价值。

## 安装方法

{example_text}

这部分最适合配合 README 里的截图一起看：先看输入是什么，再看项目产出的界面、文件或 API 结果。**能看到结果形态**，比单纯读一句功能描述更容易判断是否值得试用。

## 图文阅读建议

- **第一张图**：放仓库首页或项目速览图，让读者立刻知道项目名、语言和主题。
- **第二张图**：放 README 的 demo、架构图或界面图，解释核心能力。
- **第三张图**：自绘“输入 -> 核心模块 -> 输出 -> 场景”流程图，帮助非项目作者快速理解。

## 适合谁使用

- **开发者**：用它作为 AI 工程样例或工具链补充。
- **产品和技术负责人**：用它判断某类 AI 工具是否已有开源实现。
- **内容创作者**：用 README 截图、示例命令和功能图做图文拆解。

## 使用前要确认

**不要只看热度。** 正式采用前，建议确认 license、最近提交、issue 回复、README 示例是否能跑通。如果 README 没有安装说明、没有结果截图、issue 长期无人处理，就更适合先收藏观察。

## 项目地址

{item.canonical_url}
"""
    return {
        "title": title,
        "digest": digest,
        "markdown": markdown,
        "image_plan": default_image_plan(item),
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
                "markdown 必须以一个且仅一个 # H1 标题开头，正文小节使用 ##。"
                "正文关键短语用 **加粗**。"
                "正文要有说服力：从痛点、能力、样例、适用人群、使用限制逐步展开。"
                "功能介绍必须完整：至少覆盖输入、核心功能、输出结果、配置/扩展方式、适用场景、风险。"
                "image_plan 必须优先使用仓库原生图片、视频封面或仓库页面截图，不要生成 AI 概念图。"
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
                "要求：标题不要超过 28 个中文字符；digest 不超过 120 字；正文 1200-1800 个中文字符；"
                "markdown 包含：痛点开场、项目解决什么问题、核心功能亮点、README 功能拆解、安装方法、图文阅读建议、适用场景、使用前注意、项目地址。不要生成“项目地址与下一步建议”标题，只使用“项目地址”。"
                "写法要让读者知道它为什么值得试用：具体说清楚降低了什么成本、带来什么效果、最小上手路径是什么。"
                "image_plan.items 中每项包含 type、source、placement、caption、note，caption 要说明图片来自 README、视频封面或仓库截图。"
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
    markdown = normalize_wechat_markdown(title, str(payload.get("markdown") or fallback["markdown"]))
    if readme and "安装方法" not in markdown:
        examples = readme_code_examples(str(readme.get("markdown") or ""))
        example_text = "\n\n".join(f"```bash\n{example}\n```" for example in examples[:2])
        if example_text:
            markdown = insert_before_project_address(markdown, f"## 安装方法\n\n{example_text}")
    quality_issue = article_quality_issue(markdown)
    if quality_issue:
        markdown = normalize_wechat_markdown(fallback["title"], fallback["markdown"])
        title = fallback["title"]
        digest = fallback["digest"]
    image_plan = normalize_image_plan(payload.get("image_plan"), item)
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
            max_tokens=max(client.settings.llm_max_tokens_summary, 5000),
        )
        article = normalize_article(payload, item, raw, readme)
    except Exception as exc:
        generation_error = str(exc)

    settings = get_settings()
    readme_images = [str(image) for image in readme.get("images", []) if image]
    body_images = readme_images[:5] or [github_og_image(item)]
    if submit and settings.wechat_draft_enabled and settings.wechat_app_id and settings.wechat_app_secret:
        try:
            wechat_result = await WechatClient().add_draft(
                title=article["title"],
                digest=article["digest"],
                markdown=article["markdown"],
                content_source_url=settings.wechat_source_url or item.canonical_url,
                cover_image_url=github_og_image(item),
                body_image_urls=body_images,
            )
            submission_status = "submitted_to_wechat_draft"
            submit_result = {
                "message": "已提交到微信公众号草稿箱。",
                "media_id": wechat_result.get("media_id"),
                "thumb_media_id": wechat_result.get("thumb_media_id"),
                "uploaded_images": wechat_result.get("uploaded_images", []),
                "failed_images": wechat_result.get("failed_images", []),
                "body_images": body_images,
                "readme_images": readme.get("images", []),
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
