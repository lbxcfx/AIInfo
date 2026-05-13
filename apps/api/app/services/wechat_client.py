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


def markdown_to_wechat_html(markdown: str) -> str:
    blocks: list[str] = []
    list_items: list[str] = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            blocks.append("<ul>" + "".join(list_items) + "</ul>")
            list_items = []

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            flush_list()
            continue
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            flush_list()
            blocks.append(
                '<h2 style="font-size:22px;font-weight:700;line-height:1.45;margin:28px 0 12px;">'
                f"{inline_markdown(line[3:].strip())}</h2>"
            )
            continue
        if line.startswith("### "):
            flush_list()
            blocks.append(
                '<h3 style="font-size:18px;font-weight:700;line-height:1.5;margin:22px 0 10px;">'
                f"{inline_markdown(line[4:].strip())}</h3>"
            )
            continue
        image = re.match(r"^!\[([^\]]*)\]\((https?://[^)]+)\)$", line)
        if image:
            flush_list()
            alt = html.escape(image.group(1) or "项目截图")
            src = html.escape(image.group(2), quote=True)
            blocks.append(f'<p><img src="{src}" alt="{alt}" /></p>')
            continue
        if line.startswith(("- ", "* ")):
            list_items.append(f"<li>{inline_markdown(line[2:].strip())}</li>")
            continue
        match = re.match(r"^\d+\.\s+(.*)$", line)
        if match:
            list_items.append(f"<li>{inline_markdown(match.group(1).strip())}</li>")
            continue
        flush_list()
        blocks.append(f"<p>{inline_markdown(line)}</p>")
    flush_list()
    content = "\n".join(blocks)
    if "<h1" in content.lower():
        raise ValueError("微信正文不能包含 H1")
    return content


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
        async with httpx.AsyncClient(timeout=45, follow_redirects=True, trust_env=False) as client:
            image_response = await client.get(image_url)
            image_response.raise_for_status()
            data = image_response.content
        filename = image_filename_from_response(image_url, image_response.headers.get("content-type"), "image")
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
        for image_url in (body_image_urls or [])[:3]:
            try:
                uploaded_images.append(await self.upload_body_image(token, image_url))
            except Exception:
                continue
        image_markdown = "\n\n".join(f"![项目截图]({url})" for url in uploaded_images)
        content = markdown_to_wechat_html(f"{image_markdown}\n\n{markdown}" if image_markdown else markdown)
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
            "raw": payload,
        }
