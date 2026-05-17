from __future__ import annotations

import html
import mimetypes
import re
from pathlib import Path
from typing import Any

import httpx

from app.core.config import ROOT_DIR, get_settings


WECHAT_API_BASE = "https://api.weixin.qq.com"


class WechatApiError(RuntimeError):
    pass


def _wechat_error(payload: dict[str, Any]) -> str | None:
    errcode = payload.get("errcode")
    if errcode in (None, 0):
        return None
    return f"WeChat API error {errcode}: {payload.get('errmsg') or payload}"


def _windows_path_to_wsl(value: str) -> str:
    match = re.match(r"^([A-Za-z]):\\(.*)$", value)
    if not match:
        return value
    drive = match.group(1).lower()
    rest = match.group(2).replace("\\", "/")
    return f"/mnt/{drive}/{rest}"


def resolve_cover_path(value: str) -> Path:
    path_value = _windows_path_to_wsl(value.strip())
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


def image_filename_from_response(url: str, content_type: str | None, default_name: str) -> str:
    filename = url.rsplit("/", 1)[-1].split("?", 1)[0]
    if "." in filename:
        return filename
    if content_type and "png" in content_type:
        return f"{default_name}.png"
    if content_type and ("jpeg" in content_type or "jpg" in content_type):
        return f"{default_name}.jpg"
    if content_type and "webp" in content_type:
        return f"{default_name}.webp"
    return f"{default_name}.jpg"


def code_block_html(code_lines: list[str], language: str = "") -> str:
    code = html.escape("\n".join(code_lines).strip("\n"))
    lang = html.escape(language.strip() or "code")
    return (
        '<section style="margin:18px 0;text-align:left;">'
        '<p style="margin:0 0 6px;color:#64748b;font-size:13px;line-height:1.5;text-align:left;">'
        f'{lang} · 左右滑动查看完整命令</p>'
        '<section style="max-width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch;'
        'background:#0f172a;border-radius:8px;padding:14px 16px;text-align:left;">'
        '<pre style="margin:0;display:inline-block;min-width:100%;font-family:Menlo,Consolas,monospace;'
        'font-size:13px;line-height:1.65;color:#e2e8f0;white-space:pre;text-align:left;">'
        f'<code>{code}</code></pre></section></section>'
    )


def markdown_to_wechat_html(markdown: str) -> str:
    blocks: list[str] = []
    list_items: list[str] = []
    code_lines: list[str] = []
    code_language = ""
    in_code = False
    paragraph_style = 'style="margin:14px 0;line-height:1.8;text-align:left;word-break:break-word;"'

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            blocks.append(
                '<ul style="margin:12px 0 16px 1.2em;padding-left:0;line-height:1.8;text-align:left;">'
                + "".join(list_items)
                + "</ul>"
            )
            list_items = []

    for raw_line in markdown.splitlines():
        raw = raw_line.rstrip()
        line = raw.strip()
        if line.startswith("```"):
            if not in_code:
                flush_list()
                in_code = True
                code_language = line[3:].strip()
                code_lines = []
            else:
                blocks.append(code_block_html(code_lines, code_language))
                in_code = False
                code_language = ""
                code_lines = []
            continue
        if in_code:
            code_lines.append(raw)
            continue
        if not line:
            flush_list()
            continue
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            flush_list()
            blocks.append(
                '<h2 style="font-size:22px;font-weight:700;line-height:1.45;margin:28px 0 12px;text-align:left;">'
                f"{inline_markdown(line[3:].strip())}</h2>"
            )
            continue
        if line.startswith("### "):
            flush_list()
            blocks.append(
                '<h3 style="font-size:18px;font-weight:700;line-height:1.5;margin:22px 0 10px;text-align:left;">'
                f"{inline_markdown(line[4:].strip())}</h3>"
            )
            continue
        video_link = re.match(r"^@video_link\(([^,]+),\s*([^)]*)\)$", line)
        if video_link:
            flush_list()
            url = html.escape(video_link.group(1).strip(), quote=True)
            label = html.escape(video_link.group(2).strip() or "查看 GitHub 原生演示视频")
            blocks.append(
                '<section style="margin:18px 0;text-align:left;">'
                f'<a href="{url}" style="color:#2563eb;text-decoration:none;font-weight:700;word-break:break-all;">{label}</a>'
                '</section>'
            )
            continue
        image = re.match(r"^!\[([^\]]*)\]\((https?://[^)]+)\)$", line)
        if image:
            flush_list()
            alt = html.escape(image.group(1) or "项目配图")
            src = html.escape(image.group(2), quote=True)
            blocks.append(
                '<section style="margin:22px 0;text-align:center;">'
                f'<img src="{src}" alt="{alt}" style="max-width:100%;height:auto;display:block;margin:0 auto;" />'
                '</section>'
            )
            continue
        if line.startswith(("- ", "* ")):
            list_items.append(f'<li style="margin:6px 0;text-align:left;">{inline_markdown(line[2:].strip())}</li>')
            continue
        match = re.match(r"^\d+\.\s+(.*)$", line)
        if match:
            list_items.append(f'<li style="margin:6px 0;text-align:left;">{inline_markdown(match.group(1).strip())}</li>')
            continue
        flush_list()
        blocks.append(f"<p {paragraph_style}>{inline_markdown(line)}</p>")
    flush_list()
    if in_code:
        blocks.append(code_block_html(code_lines, code_language))
    content = "\n".join(blocks)
    if "<h1" in content.lower():
        raise ValueError("微信正文不能包含 H1")
    return content


def _section_end(markdown: str, heading_start: int) -> int:
    next_heading = re.search(r"(?m)^## ", markdown[heading_start + 1 :])
    if not next_heading:
        return len(markdown)
    return heading_start + 1 + next_heading.start()


def _insert_after_first_matching_section(markdown: str, keywords: tuple[str, ...], block: str) -> tuple[str, bool]:
    for match in re.finditer(r"(?m)^## .+$", markdown):
        heading = match.group(0)
        if any(keyword in heading for keyword in keywords):
            end = _section_end(markdown, match.start())
            return markdown[:end].rstrip() + "\n\n" + block + "\n\n" + markdown[end:].lstrip(), True
    return markdown, False


def _insert_before_project_or_append(markdown: str, block: str) -> str:
    marker = re.search(r"(?m)^## 项目地址\s*$", markdown)
    if marker:
        return markdown[: marker.start()].rstrip() + "\n\n" + block + "\n\n" + markdown[marker.start():].lstrip()
    return markdown.rstrip() + "\n\n" + block


def insert_uploaded_images(markdown: str, uploaded_images: list[str]) -> str:
    if not uploaded_images:
        return markdown
    captions = [
        "图 1｜仓库原生配图：结合上下文查看项目界面、架构、演示或仓库首屏。",
        "图 2｜仓库原生配图：补充展示 README 中的界面、流程或运行效果。",
        "图 3｜仓库补充配图：用于补充项目页面中的视觉证据。",
    ]
    result = markdown
    first = f"![{captions[0]}]({uploaded_images[0]})"
    result, inserted = _insert_after_first_matching_section(result, ("痛点", "解决什么问题"), first)
    if not inserted:
        result = _insert_before_project_or_append(result, first)
    if len(uploaded_images) >= 2:
        second = f"![{captions[1]}]({uploaded_images[1]})"
        result, inserted = _insert_after_first_matching_section(result, ("核心", "功能拆解", "能力", "README"), second)
        if not inserted:
            result = _insert_before_project_or_append(result, second)
    for index, url in enumerate(uploaded_images[2:], start=2):
        caption = captions[index] if index < len(captions) else f"图 {index + 1}｜项目补充配图。"
        result = _insert_before_project_or_append(result, f"![{caption}]({url})")
    return result

def inline_markdown(value: str) -> str:
    escaped = html.escape(value)
    escaped = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>',
        escaped,
    )
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped


class WechatClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def access_token(self) -> str:
        if not self.settings.wechat_app_id or not self.settings.wechat_app_secret:
            raise WechatApiError("未配置 WECHAT_APPID/WECHAT_APPSECRET")
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            response = await client.get(
                f"{WECHAT_API_BASE}/cgi-bin/token",
                params={
                    "grant_type": "client_credential",
                    "appid": self.settings.wechat_app_id,
                    "secret": self.settings.wechat_app_secret,
                },
            )
            response.raise_for_status()
            payload = response.json()
        error = _wechat_error(payload)
        if error:
            raise WechatApiError(error)
        token = payload.get("access_token")
        if not token:
            raise WechatApiError("微信 access_token 响应缺少 access_token")
        return str(token)

    async def thumb_media_id(self, token: str, cover_override: str | None = None) -> str:
        if self.settings.wechat_thumb_media_id:
            return self.settings.wechat_thumb_media_id
        cover = (cover_override or self.settings.wechat_cover_image).strip()
        if not cover:
            raise WechatApiError("未配置 WECHAT_COVER_IMAGE 或 WECHAT_THUMB_MEDIA_ID，无法创建微信草稿封面")
        if cover.startswith(("http://", "https://")):
            async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
                image_response = await client.get(cover)
                image_response.raise_for_status()
                data = image_response.content
            filename = image_filename_from_response(cover, image_response.headers.get("content-type"), "cover")
        else:
            path = resolve_cover_path(cover)
            if not path.exists():
                raise WechatApiError(f"微信封面文件不存在：{path}")
            data = path.read_bytes()
            filename = path.name

        mime_type = mimetypes.guess_type(filename)[0] or "image/jpeg"
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            response = await client.post(
                f"{WECHAT_API_BASE}/cgi-bin/material/add_material",
                params={"access_token": token, "type": "thumb"},
                files={"media": (filename, data, mime_type)},
            )
            response.raise_for_status()
            payload = response.json()
        error = _wechat_error(payload)
        if error:
            raise WechatApiError(error)
        media_id = payload.get("media_id")
        if not media_id:
            raise WechatApiError(f"微信封面上传响应缺少 media_id：{payload}")
        return str(media_id)

    async def upload_body_image(self, token: str, image_url: str) -> str:
        if image_url.startswith(("http://", "https://")):
            async with httpx.AsyncClient(timeout=45, follow_redirects=True, trust_env=False) as client:
                image_response = await client.get(image_url)
                image_response.raise_for_status()
                data = image_response.content
            filename = image_filename_from_response(image_url, image_response.headers.get("content-type"), "image")
        else:
            path_value = image_url.removeprefix("file://")
            path = resolve_cover_path(path_value)
            if not path.exists():
                raise WechatApiError(f"微信正文图片文件不存在：{path}")
            data = path.read_bytes()
            filename = path.name
        mime_type = mimetypes.guess_type(filename)[0] or "image/png"
        if mime_type not in {"image/jpeg", "image/png"}:
            raise WechatApiError(f"微信正文图片仅上传 jpg/png，当前为 {mime_type}")
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            response = await client.post(
                f"{WECHAT_API_BASE}/cgi-bin/media/uploadimg",
                params={"access_token": token},
                files={"media": (filename, data, mime_type)},
            )
            response.raise_for_status()
            payload = response.json()
        error = _wechat_error(payload)
        if error:
            raise WechatApiError(error)
        url = payload.get("url")
        if not url:
            raise WechatApiError(f"微信正文图片上传响应缺少 url：{payload}")
        return str(url)

    async def add_draft(
        self,
        *,
        title: str,
        digest: str,
        markdown: str,
        content_source_url: str,
        cover_image_url: str | None = None,
        body_image_urls: list[str] | None = None,
    ) -> dict[str, Any]:
        token = await self.access_token()
        thumb_media_id = await self.thumb_media_id(token, cover_image_url)
        uploaded_images: list[str] = []
        failed_images: list[dict[str, str]] = []
        for image_url in (body_image_urls or [])[:5]:
            last_error: Exception | None = None
            for _attempt in range(2):
                try:
                    uploaded_images.append(await self.upload_body_image(token, image_url))
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
            if last_error:
                failed_images.append({"source": image_url, "error": str(last_error)})
                continue
        content_markdown = insert_uploaded_images(markdown, uploaded_images)
        content = markdown_to_wechat_html(content_markdown)
        article = {
            "title": title[:64],
            "author": self.settings.wechat_author[:8] or "AI 情报站",
            "digest": digest[:120],
            "content": content,
            "content_source_url": content_source_url[:255],
            "thumb_media_id": thumb_media_id,
            "need_open_comment": 0,
            "only_fans_can_comment": 0,
        }
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            response = await client.post(
                f"{WECHAT_API_BASE}/cgi-bin/draft/add",
                params={"access_token": token},
                json={"articles": [article]},
            )
            response.raise_for_status()
            payload = response.json()
        error = _wechat_error(payload)
        if error:
            raise WechatApiError(error)
        return {
            "media_id": payload.get("media_id"),
            "thumb_media_id": thumb_media_id,
            "uploaded_images": uploaded_images,
            "failed_images": failed_images,
            "raw": payload,
        }
