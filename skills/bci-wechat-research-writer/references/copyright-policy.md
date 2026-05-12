# Copyright And Screenshot Policy

Use this reference before extracting screenshots, figures, tables, or long text from papers.

## Default Position

Respect copyright and publisher terms. Do not reproduce closed-access figures or large text passages by default. Prefer:

- self-made explanatory diagrams,
- redrawn method flows based on factual understanding,
- original charts from extracted numeric data when allowed,
- short paraphrases with source links,
- open-access figures with license notes.

## Allowed With Lower Risk

- arXiv source figures when the arXiv paper license permits reuse, with attribution.
- PMC/open-access article figures under a compatible Creative Commons license.
- User-provided screenshots when the user confirms they have rights to use them.
- Self-made diagrams that do not trace or copy protected figure composition.

## Higher Risk

- Nature/Springer/Elsevier/IEEE figures without explicit reuse rights.
- Full-page screenshots of closed publisher articles.
- Reproducing figure panels that are central creative expression of the article.
- Long verbatim excerpts from abstracts, results, or discussion.

## Practical Rules

- Keep direct quotes short and necessary.
- Attribute every figure or screenshot.
- Store a `figure_manifest.md` or equivalent notes with source, license, and rationale.
- If license is unclear, use a self-made diagram and link the original paper.
- For WeChat publishing, avoid relying on fair use as the only justification unless the user explicitly accepts that risk.

## Figure Manifest Fields

```markdown
| file | type | source | original figure/page | license/permission | rationale |
|---|---|---|---|---|---|
| images/system-flow.png | redrawn diagram | Paper methods | Figure 1 concept | self-made from facts | Explains system pipeline |
```
