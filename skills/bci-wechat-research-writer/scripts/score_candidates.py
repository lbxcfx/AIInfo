#!/usr/bin/env python3
"""Rank BCI paper candidates from JSONL.

Input: one JSON object per line. Output: Markdown table by default, JSONL with
--jsonl. This helper provides a first-pass editorial score; Codex should still
verify papers and evidence before writing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

VENUE_WEIGHTS = {
    "nature": 18,
    "science": 18,
    "cell": 16,
    "nejm": 16,
    "lancet": 16,
    "neuron": 14,
    "nature neuroscience": 16,
    "nature biomedical engineering": 17,
    "nature machine intelligence": 15,
    "science translational medicine": 15,
    "pnas": 11,
    "brain": 11,
    "journal of neural engineering": 9,
    "ieee transactions on neural systems and rehabilitation engineering": 9,
    "arxiv": 3,
    "biorxiv": 3,
    "medrxiv": 3,
}

BCI_TERMS = [
    "brain-computer interface",
    "brain-computer interfaces",
    "brain computer interface",
    "brain computer interfaces",
    "brain-machine interface",
    "brain-machine interfaces",
    "brain machine interface",
    "brain machine interfaces",
    "bci",
    "bcis",
    "neural decoding",
    "neuroprosthesis",
    "neuroprosthetic",
    "ecog",
    "eeg",
    "intracortical",
    "motor imagery",
    "closed-loop",
    "speech decoding",
    "neural spike",
    "spike data",
    "invasive neural",
    "motor-imagery",
    "mi-bci",
]

IMPACT_TERMS = [
    "human",
    "patient",
    "clinical",
    "trial",
    "speech",
    "paralysis",
    "tetraplegia",
    "als",
    "real-time",
    "online",
    "closed-loop",
    "implant",
    "invasive",
    "bidirectional",
    "sensory feedback",
    "foundation model",
    "pretrained model",
    "general-purpose",
]

OFF_TOPIC_TERMS = [
    "syndrome-based neural decoding",
    "code automorphisms",
    "high-fidelity music generation",
    "acoustic token",
    "tactile simulation",
    "elastomer deformation",
    "robotic interaction",
]


def text_blob(paper: dict[str, Any]) -> str:
    fields = [
        paper.get("title", ""),
        paper.get("abstract", ""),
        paper.get("venue", ""),
        paper.get("source", ""),
        " ".join(paper.get("fields", []) or []),
    ]
    return " ".join(str(x) for x in fields).lower()


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, int):
        return date(value, 1, 1)
    value = str(value)
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y"):
        try:
            return datetime.strptime(value[:10] if fmt != "%Y" else value[:4], fmt).date()
        except ValueError:
            pass
    return None


def recency_score(paper: dict[str, Any]) -> int:
    published = parse_date(paper.get("published") or paper.get("date") or paper.get("year"))
    if not published:
        return 0
    days = (date.today() - published).days
    if days <= 30:
        return 10
    if days <= 90:
        return 7
    if days <= 365:
        return 4
    return 0


def venue_score(paper: dict[str, Any]) -> int:
    venue = f"{paper.get('venue', '')} {paper.get('source', '')}".lower()
    score = 0
    for key, weight in VENUE_WEIGHTS.items():
        if key in venue:
            score = max(score, weight)
    return score


def term_score(blob: str, terms: list[str], weight: int) -> tuple[int, list[str]]:
    hits = [term for term in terms if re.search(r"\b" + re.escape(term) + r"\b", blob)]
    return min(len(hits) * weight, 20), hits


def score_paper(paper: dict[str, Any]) -> dict[str, Any]:
    blob = text_blob(paper)
    bci_score, bci_hits = term_score(blob, BCI_TERMS, 4)
    impact_score, impact_hits = term_score(blob, IMPACT_TERMS, 3)
    off_topic_hits = [term for term in OFF_TOPIC_TERMS if term in blob]
    citations = int(paper.get("citation_count") or paper.get("cited_by_count") or 0)
    citation_score = min(citations // 10, 12)
    open_score = 3 if paper.get("is_open_access") or paper.get("has_pdf") else 0
    code_score = 3 if paper.get("has_code") or paper.get("code_url") else 0
    total = (
        bci_score
        + impact_score
        + citation_score
        + venue_score(paper)
        + recency_score(paper)
        + open_score
        + code_score
        - (len(off_topic_hits) * 12)
    )
    out = dict(paper)
    out["editorial_score"] = total
    out["bci_hits"] = bci_hits
    out["impact_hits"] = impact_hits
    out["off_topic_hits"] = off_topic_hits
    return out


def read_jsonl(path: str) -> list[dict[str, Any]]:
    if path == "-":
        content = sys.stdin.read()
    else:
        raw = open(path, "rb").read()
        for encoding in ("utf-8-sig", "utf-16"):
            try:
                content = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            content = raw.decode("utf-8", errors="replace")

    papers = []
    for line_no, line in enumerate(content.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            papers.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON on line {line_no}: {exc}") from exc
    return papers


def md_escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def print_markdown(papers: list[dict[str, Any]], limit: int) -> None:
    print("| score | title | venue/source | date | why it may matter | url |")
    print("|---:|---|---|---|---|---|")
    for p in papers[:limit]:
        why = ", ".join((p.get("impact_hits") or [])[:4]) or ", ".join((p.get("bci_hits") or [])[:4])
        venue = p.get("venue") or p.get("source") or ""
        published = p.get("published") or p.get("date") or p.get("year") or ""
        print(
            f"| {p['editorial_score']} | {md_escape(p.get('title'))} | "
            f"{md_escape(venue)} | {md_escape(published)} | {md_escape(why)} | {md_escape(p.get('url'))} |"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank BCI paper candidates from JSONL.")
    parser.add_argument("input", help="JSONL file path, or - for stdin")
    parser.add_argument("--limit", type=int, default=20, help="Rows to print in Markdown mode")
    parser.add_argument("--jsonl", action="store_true", help="Emit scored JSONL instead of Markdown")
    args = parser.parse_args()

    papers = [score_paper(p) for p in read_jsonl(args.input)]
    papers.sort(key=lambda p: p["editorial_score"], reverse=True)
    if args.jsonl:
        for paper in papers:
            print(json.dumps(paper, ensure_ascii=False))
    else:
        print_markdown(papers, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
