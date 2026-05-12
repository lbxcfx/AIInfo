#!/usr/bin/env python3
"""Build a WeChat article Markdown skeleton from a selected paper JSON file."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

def load_paper(path: str) -> dict[str, Any]:
    if path == "-":
        text = sys.stdin.read().strip()
    else:
        raw = open(path, "rb").read()
        for encoding in ("utf-8-sig", "utf-16"):
            try:
                text = raw.decode(encoding).strip()
                break
            except UnicodeDecodeError:
                continue
        else:
            text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        raise SystemExit("Empty input")
    if "\n" in text:
        text = text.splitlines()[0]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON: {exc}") from exc


def join_authors(authors: Any) -> str:
    if isinstance(authors, list):
        return ", ".join(str(a) for a in authors[:6]) + (" 等" if len(authors) > 6 else "")
    return str(authors or "")


def paper_ref(p: dict[str, Any]) -> str:
    parts = [join_authors(p.get("authors")), p.get("title"), p.get("venue") or p.get("source"), p.get("year")]
    head = ". ".join(str(x) for x in parts if x)
    ids = []
    for key, label in (("doi", "DOI"), ("arxiv_id", "arXiv"), ("pmid", "PMID")):
        if p.get(key):
            ids.append(f"{label}: {p[key]}")
    if p.get("url"):
        ids.append(f"URL: {p['url']}")
    return f"- {head}. {'; '.join(ids)}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Chinese WeChat article skeleton from paper JSON.")
    parser.add_argument("input", help="JSON file/JSONL first line, or - for stdin")
    parser.add_argument("--title", help="Override article title")
    parser.add_argument("--digest", help="Override one-sentence digest")
    args = parser.parse_args()

    p = load_paper(args.input)
    title = args.title or f"这篇脑机接口论文值得关注：{p.get('title', '待补标题')}"
    digest = args.digest or "待补：用一句话说明这篇论文真正推进了什么，以及为什么值得读者关注。"
    abstract = p.get("abstract") or "待补：摘要和核心问题。"

    print(f"# {title}\n")
    print(f"> 一句话导读：{digest}\n")
    print("## 这篇文章讲了什么\n")
    print(f"{abstract}\n")
    print("<!-- evidence: title/abstract/source metadata verified before publishing -->\n")
    print("## 为什么它重要\n")
    print("- 待补：它解决了 BCI 哪个关键瓶颈？")
    print("- 待补：相比已有工作，新的能力、场景或证据是什么？\n")
    print("## 研究团队怎么做的\n")
    print("- 待补：受试者/数据来源。")
    print("- 待补：信号采集方式、模型、训练和在线/离线设置。")
    print("- 待补：评价指标和基线。\n")
    print("## 最关键的结果\n")
    print("- 待补：结果 1，绑定 figure/table/page。")
    print("- 待补：结果 2，绑定 figure/table/page。")
    print("- 待补：结果 3，绑定 figure/table/page。\n")
    print("## 图解：方法和系统流程\n")
    print("![待补方法图](images/method-flow.png)\n")
    print("图注：待补。来源：作者自绘 / 根据论文方法重绘 / 论文开放许可图。\n")
    print("## 和过去工作的差异\n")
    print("待补：从任务、数据、模型、在线性能、临床意义等角度比较。\n")
    print("## 仍然需要冷静看的问题\n")
    print("- 待补：样本量、泛化、长期稳定性、延迟、安全、隐私或临床转化限制。")
    print("- 待补：如果是预印本，说明尚未同行评审。\n")
    print("## 对脑机接口领域的启发\n")
    print("待补：对研究、产品、临床或产业的具体启发。\n")
    print("## 参考资料\n")
    print(paper_ref(p))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
