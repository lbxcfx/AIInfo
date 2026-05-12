from __future__ import annotations

import hashlib
import re
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"ref", "ref_src", "fbclid", "gclid", "mc_cid", "mc_eid"}


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key not in TRACKING_KEYS and not key.startswith(TRACKING_PREFIXES)
    ]
    clean_path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            clean_path,
            urlencode(query, doseq=True),
            "",
        )
    )


def stable_hash(*parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8", errors="ignore"))
        digest.update(b"\0")
    return digest.hexdigest()


def clean_text(value: str | None, max_length: int | None = None) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if max_length and len(text) > max_length:
        return text[: max_length - 1].rstrip() + "..."
    return text


AI_KEYWORDS = [
    "ai",
    "artificial intelligence",
    "llm",
    "large language model",
    "agent",
    "model",
    "openai",
    "anthropic",
    "claude",
    "gemini",
    "deepmind",
    "hugging face",
    "transformer",
    "diffusion",
    "embedding",
    "inference",
    "fine-tuning",
    "机器学习",
    "人工智能",
    "大模型",
    "智能体",
]


def ai_relevance_score(title: str, content: str) -> float:
    haystack = f"{title} {content}".lower()
    hits = sum(1 for keyword in AI_KEYWORDS if keyword in haystack)
    if hits == 0:
        return 0.2
    return min(0.98, 0.55 + hits * 0.08)


def classify_category(title: str, content: str) -> str:
    haystack = f"{title} {content}".lower()
    if any(word in haystack for word in ["paper", "arxiv", "research", "benchmark", "论文"]):
        return "论文研究"
    if any(word in haystack for word in ["release", "launch", "announces", "introducing", "发布"]):
        return "模型发布/更新" if "model" in haystack or "模型" in haystack else "产品发布/更新"
    if any(word in haystack for word in ["github", "tool", "api", "sdk", "product", "app"]):
        return "产品发布/更新"
    if any(word in haystack for word in ["how to", "guide", "tutorial", "技巧", "观点"]):
        return "技巧与观点"
    return "行业动态"


def heuristic_final_score(source_tier: str, relevance: float, category: str) -> float:
    tier_weight = {"T1": 16, "T1_5": 10, "T2": 4, "T3": 0}.get(source_tier, 4)
    category_weight = {
        "模型发布/更新": 10,
        "产品发布/更新": 8,
        "论文研究": 6,
        "行业动态": 4,
        "技巧与观点": 3,
    }.get(category, 4)
    return round(min(99.0, relevance * 70 + tier_weight + category_weight), 1)

