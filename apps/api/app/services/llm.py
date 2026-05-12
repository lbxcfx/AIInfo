from __future__ import annotations

import json
import re
from typing import Any

from openai import AsyncOpenAI

from app.core.config import get_settings


class BigModelClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.client = AsyncOpenAI(
            api_key=settings.zai_api_key,
            base_url=settings.bigmodel_base_url,
            timeout=settings.bigmodel_timeout_seconds,
            max_retries=settings.bigmodel_max_retries,
        )

    async def ping_chat(self, model: str | None = None) -> str:
        selected_model = model or self.settings.llm_model_relevance
        response = await self.client.chat.completions.create(
            model=selected_model,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            temperature=0,
            max_tokens=300,
        )
        return response.choices[0].message.content or ""

    async def chat_json(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 3000,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        return parse_json_object(content), {
            "prompt_tokens": getattr(response.usage, "prompt_tokens", None),
            "completion_tokens": getattr(response.usage, "completion_tokens", None),
            "total_tokens": getattr(response.usage, "total_tokens", None),
        }

    async def embed_one(self, text: str) -> list[float]:
        response = await self.client.embeddings.create(
            model=self.settings.embedding_model,
            input=[text],
            dimensions=self.settings.embedding_dimensions,
        )
        return list(response.data[0].embedding)


def parse_json_object(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.S)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("model response is not a JSON object")
    return parsed
