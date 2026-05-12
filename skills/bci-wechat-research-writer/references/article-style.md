# Article Style

Use this reference when writing Chinese WeChat public-account articles.

## Target Reader

Write for technically curious readers: AI researchers, neuroscience readers, clinicians, founders, investors, and advanced students. Explain domain terms briefly, but do not dilute the science.

## Recommended Structure

```markdown
# 标题

> 一句话导读：这篇论文真正推进了什么，以及为什么值得关注。

## 这篇文章讲了什么

## 为什么它重要

## 研究团队怎么做的

## 最关键的结果

## 图解：方法和系统流程

## 和过去工作的差异

## 仍然需要冷静看的问题

## 对脑机接口产业/临床/研究的启发

## 参考资料
```

## Title Rules

- Make the title specific: subject + breakthrough/result + context.
- Avoid sensational claims such as "读心术成真", "治愈瘫痪", "颠覆人类".
- Use numbers only when they are central and verified.
- For preprints, do not imply peer-reviewed validation.

## Tone

- Use clear Chinese prose with short paragraphs.
- Prefer concrete explanations over hype.
- Distinguish "paper shows", "authors claim", "data suggests", and "still unknown".
- Explain why a figure/table matters, not only what it displays.
- Include a limitation section even for exciting papers.

## Evidence Formatting

Use compact evidence notes while drafting:

```markdown
<!-- evidence: Figure 2, online decoding accuracy; Table 1, cohort size; Abstract, main claim -->
```

Remove internal comments before publishing unless the user wants an editorial audit trail.

## Image Captions

Each image should have:

```markdown
![简洁说明](images/example.png)

图注：说明图中最重要的信息。来源：论文 Figure 2 / 作者自绘 / 根据论文方法重绘。
```

## Reference Format

```markdown
- Author et al. Title. Venue, Year. DOI/arXiv/PMID: ...
- Official paper page: ...
- Code/data: ...
```

## WeChat Handoff

Before sending to a Markdown-to-WeChat tool:

- Keep heading levels shallow: H1 title, H2 major sections, H3 only when necessary.
- Prefer local image paths and concise alt text.
- Keep paragraphs short enough for mobile reading.
- Add a digest/summary of 60-120 Chinese characters.
- Prepare a cover image or a first image suitable as the cover.
