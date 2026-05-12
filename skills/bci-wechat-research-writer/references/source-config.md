# Source Configuration

Use this reference when discovering BCI papers or verifying metadata.

## Source Priority

1. **arXiv** for preprints in cs.HC, cs.LG, cs.AI, eess.SP, q-bio.NC, stat.ML.
2. **bioRxiv/medRxiv** for neuroscience, clinical BCI, neuroprosthetics, and rehabilitation preprints.
3. **PubMed/PMC** for peer-reviewed biomedical records and open-access full text.
4. **Semantic Scholar** for citation count, influential citations, related papers, author disambiguation, and paper recommendations.
5. **OpenAlex/Crossref** for DOI normalization, venue metadata, publication dates, and cited-by counts.
6. **Springer Nature/Nature.com** for Nature-family metadata and open abstracts. Prefer official pages and APIs where available.

Use at least two sources for "important paper" selection whenever possible: a discovery source plus an enrichment/verification source.

## Query Templates

Core English query terms:

```text
"brain-computer interface" OR "brain machine interface" OR BCI
"neural decoding" OR "speech decoding" OR "motor decoding"
"intracortical" OR ECoG OR EEG OR MEG
"neural prosthesis" OR neuroprosthetic OR "closed-loop neurostimulation"
"motor imagery" OR "cursor control" OR "text entry"
```

High-impact query modifiers:

```text
human OR patient OR participant OR clinical OR trial
speech OR handwriting OR paralysis OR tetraplegia OR ALS
closed-loop OR online OR real-time
Nature OR Science OR Cell OR NEJM OR Lancet
```

Example arXiv query:

```text
(all:"brain-computer interface" OR all:"brain machine interface" OR all:"neural decoding" OR all:"neuroprosthesis") AND (all:human OR all:speech OR all:motor OR all:closed-loop)
```

Example PubMed query:

```text
("brain-computer interfaces"[MeSH Terms] OR "brain-computer interface"[Title/Abstract] OR "brain machine interface"[Title/Abstract] OR "neural decoding"[Title/Abstract]) AND ("humans"[MeSH Terms] OR human[Title/Abstract] OR patient[Title/Abstract])
```

## Metadata Fields To Collect

- title
- abstract
- authors
- publication date
- source database
- venue/journal/server
- DOI/arXiv ID/PMID/PMCID
- URL and PDF URL
- citation count or cited-by count
- open-access flag
- code/data links
- paper type: preprint, peer-reviewed article, review, dataset, benchmark, press release

## Discovery Rules

- Deduplicate before scoring.
- Treat arXiv/bioRxiv/medRxiv papers as preprints unless a peer-reviewed version is verified.
- Do not treat press releases as primary evidence; use them only for context.
- Prefer official metadata pages over reposts and news summaries.
- Record API query date for reproducibility.

## Rate And Access Notes

- arXiv API requests should be spaced; avoid rapid polling.
- PubMed E-utilities requests should include an email/tool identifier when available.
- Springer Nature and some Semantic Scholar endpoints may need API keys.
- WeChat publishing requires valid official-account credentials, IP allowlist, media upload permissions, and draft API access.
