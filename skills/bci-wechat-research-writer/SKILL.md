---
name: bci-wechat-research-writer
description: Research and draft Chinese WeChat public-account articles about high-impact brain-computer interface papers. Use when Codex needs to discover recent BCI papers from arXiv, bioRxiv/medRxiv, PubMed, Semantic Scholar, OpenAlex, Nature/Springer sources; rank candidates; analyze a selected paper with evidence; extract or plan key figures/screenshots; produce a reader-friendly Markdown article; and prepare publishing checks for WeChat draft-box workflows.
---

# BCI WeChat Research Writer

## Overview

Use this skill to run an editorial workflow for brain-computer interface (BCI) papers: discover candidates, select a worthwhile paper, analyze it with evidence, prepare figures legally, write a Chinese WeChat article, and hand off to a WeChat Markdown/draft-box tool such as `md2wechat-skill`.

Do not publish automatically unless the user explicitly asks for draft-box upload and the required WeChat credentials, IP allowlist, cover image, and preview checks are ready.

## Workflow

1. **Clarify scope only when necessary**
   - Default topic: recent high-impact BCI/neural interface papers.
   - Default recency: last 14 days for news-like requests, last 90 days for deeper roundups.
   - Default language: Chinese, public-account style, technically accurate but readable.
   - Ask before uploading to WeChat or using paid/protected APIs.

2. **Discover papers**
   - Use `references/source-config.md` for source priority, official API notes, rate limits, and query templates.
   - Use `references/bci-taxonomy.md` for BCI keywords and subfield classification.
   - Search at least two independent sources when possible: one preprint/source database and one enrichment database such as Semantic Scholar or OpenAlex.
   - Deduplicate by DOI, arXiv ID, PMID, title fingerprint, and first-author/year.

3. **Rank candidates**
   - Prefer papers with strong evidence of importance: Nature-family or top clinical/neuroscience venue, major BCI capability improvement, human-subject result, strong institution/team, open code/data, important limitation or controversy.
   - Use `scripts/score_candidates.py` on a JSONL candidate list when candidates are already collected.
   - Output a short candidate table before deep writing unless the user already selected a paper.

4. **Analyze the selected paper**
   - Build an evidence ledger before writing. Every major claim must map to title/abstract/full-text passage, figure/table, metric, or method detail.
   - For arXiv papers, prefer source extraction when available; use PDF extraction as fallback.
   - For PubMed/PMC/open-access papers, prefer official XML/HTML where available.
   - For closed publisher pages, use metadata, abstract, press release, and short compliant quotes only; do not reproduce large copyrighted passages or figures.

5. **Plan figures and screenshots**
   - Follow `references/copyright-policy.md`.
   - Prefer self-made explanatory diagrams, redrawn method flows, and table summaries for closed-access or unclear-license content.
   - For each image, record: source, license/permission assumption, original figure/page, caption, and why it is needed.
   - Use screenshots only when the source license and fair-use/editorial rationale are acceptable for the user's jurisdiction and publishing risk.

6. **Write the article**
   - Follow `references/article-style.md`.
   - Use `scripts/build_article_skeleton.py` to create a Markdown skeleton when starting from a selected paper JSON object.
   - Keep the article useful for readers: why it matters, what changed, how it works, what the result proves, what it does not prove, and what to watch next.
   - Include references at the end with DOI/arXiv/PMID/source links.

7. **Prepare WeChat handoff**
   - Produce clean Markdown with local image paths.
   - If `md2wechat-skill` is installed, use it for conversion, preview, image upload, cover selection, and draft-box push.
   - Before draft-box upload, verify title, author/source line, digest, cover, image licensing notes, and preview rendering.

## Candidate Input Format

Scripts expect JSONL, one paper per line. Use these fields when available:

```json
{"title":"...","abstract":"...","authors":["..."],"year":2026,"published":"2026-05-01","source":"arxiv","url":"https://...","doi":"...","arxiv_id":"...","venue":"...","citation_count":12,"fields":["brain-computer interface"],"is_open_access":true,"has_pdf":true,"has_code":false}
```

Missing fields are allowed. Scripts are helper utilities; Codex should still inspect the actual papers and evidence before writing.

## Quality Gates

Before presenting or uploading an article, check:

- The selected paper is actually about BCI/neural interface, not just generic neuroscience or ML.
- Main claims are backed by explicit evidence from the paper or reliable metadata.
- The article distinguishes peer-reviewed papers from preprints.
- Screenshots and figures have source and license notes.
- No large copyrighted text or unsupported figure reproduction is included.
- Limitations are concrete, not boilerplate.
- The WeChat title is compelling but does not overclaim clinical readiness, mind-reading, cure, or AGI-like claims.

## Resource Guide

- `references/source-config.md`: source/API strategy and query templates.
- `references/bci-taxonomy.md`: BCI categories, keywords, and exclusion rules.
- `references/article-style.md`: Chinese WeChat article structure and tone.
- `references/copyright-policy.md`: figure/screenshot and quote rules.
- `scripts/search_arxiv.py`: query arXiv and emit candidate JSONL.
- `scripts/score_candidates.py`: rank paper candidates from JSONL.
- `scripts/build_article_skeleton.py`: create a Markdown article scaffold from one selected paper JSON object.
