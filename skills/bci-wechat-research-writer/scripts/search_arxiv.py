#!/usr/bin/env python3
"""Search arXiv and emit BCI paper candidates as JSONL.

This script uses only the Python standard library. It is intentionally small:
Codex should still enrich results with Semantic Scholar/OpenAlex/PubMed before
claiming a paper is "high impact".
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"
DEFAULT_QUERY = (
    'all:"brain-computer interface" OR all:"brain machine interface" OR '
    'all:"neural decoding" OR all:"neuroprosthesis" OR all:"speech decoding"'
)


def build_url(query: str, start: int, max_results: int, sort_by: str, sort_order: str) -> str:
    params = {
        "search_query": query,
        "start": str(start),
        "max_results": str(max_results),
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }
    return "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)


def text(elem: ET.Element | None) -> str:
    return "" if elem is None or elem.text is None else " ".join(elem.text.split())


def parse_entry(entry: ET.Element) -> dict[str, Any]:
    arxiv_url = text(entry.find(f"{ATOM}id"))
    arxiv_id = arxiv_url.rsplit("/", 1)[-1] if arxiv_url else ""
    pdf_url = ""
    for link in entry.findall(f"{ATOM}link"):
        if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
            pdf_url = link.attrib.get("href", "")
    authors = [text(a.find(f"{ATOM}name")) for a in entry.findall(f"{ATOM}author")]
    categories = [c.attrib.get("term", "") for c in entry.findall(f"{ATOM}category")]
    return {
        "title": text(entry.find(f"{ATOM}title")),
        "abstract": text(entry.find(f"{ATOM}summary")),
        "authors": authors,
        "published": text(entry.find(f"{ATOM}published"))[:10],
        "updated": text(entry.find(f"{ATOM}updated"))[:10],
        "source": "arxiv",
        "venue": "arXiv",
        "url": arxiv_url,
        "pdf_url": pdf_url,
        "arxiv_id": arxiv_id,
        "fields": categories,
        "is_open_access": True,
        "has_pdf": bool(pdf_url),
    }


def fetch(url: str, user_agent: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def main() -> int:
    parser = argparse.ArgumentParser(description="Search arXiv and emit JSONL candidate papers.")
    parser.add_argument("--query", default=DEFAULT_QUERY, help="arXiv search_query expression")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--max-results", type=int, default=25)
    parser.add_argument("--sort-by", default="submittedDate", choices=["relevance", "lastUpdatedDate", "submittedDate"])
    parser.add_argument("--sort-order", default="descending", choices=["ascending", "descending"])
    parser.add_argument("--user-agent", default="bci-wechat-research-writer/0.1")
    parser.add_argument("--dry-run", action="store_true", help="Print request URL without fetching")
    parser.add_argument("--sleep", type=float, default=3.0, help="Delay before request to respect arXiv pacing")
    args = parser.parse_args()

    url = build_url(args.query, args.start, args.max_results, args.sort_by, args.sort_order)
    if args.dry_run:
        print(url)
        return 0

    if args.sleep > 0:
        time.sleep(args.sleep)
    try:
        data = fetch(url, args.user_agent)
    except Exception as exc:  # pragma: no cover - network/environment dependent
        print(f"arXiv request failed: {exc}", file=sys.stderr)
        return 2

    root = ET.fromstring(data)
    for entry in root.findall(f"{ATOM}entry"):
        print(json.dumps(parse_entry(entry), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
