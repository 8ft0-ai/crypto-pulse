## Reading this archive

CryptoPulse is an AI-generated crypto market **demonstration and archive**, not a live market-data service or professional investment research. The article is a reading view of a preserved report. Its publication time is not a promise that source observations remain current. An older report is historical even when it is the most recently available report.

A canonical article presents supported findings first. The supporting-evidence section provides source links and observation windows; the original report and technical record remain accessible through the disclosure on the same page. This methodology describes reusable rules, not additional findings about any particular market event.

## Source records and observation semantics

Archived JSON snapshots preserve source-reported market values and associated timestamps. A snapshot's generation time and an individual source observation's time are different concepts. Price changes over a reported rolling seven-day window are *source-reported metrics*, not independently reconstructed returns. An archived interval comparison uses two independently preserved observations, not continuous intra-interval data.

The article's **pinned source-snapshot links** identify repository JSON records by path and exact Git commit, with SHA-256 content digests. Those references are distinct from source names or citation markers embedded in the **original archived Markdown report**. A cited report is not automatically a validated snapshot; likewise, the absence of an extracted Markdown source list does not establish that no JSON source exists.

The original Markdown can be opened at the exact site-build commit. Its preserved wording and citations are historical publication records. Their preservation does not retrospectively validate historical AI interpretations.

## Deterministic and AI-generated material

The site includes historical AI-generated Markdown reports and more recent deterministic reports. The entire publication remains a demo, but a deterministic report with 'llm_generated: false' must not be described as a fresh LLM conclusion. The typed 'cryptopulse-editorial-article/v1' display derives from the same source-validated deterministic assessment used to produce its Markdown report. The static site renderer does not perform new market analysis.

Legacy Markdown-only reports retain their original text, not a reconstructed modern finding. An old report's source citation or narrative assertion is not promoted to a new deterministic market claim.

## Validation, alignment and freshness

Evidence eligibility depends on the repository's required source and snapshot-quality checks. A 'valid-ok' quality status indicates acceptance under those checks; it does **not** certify a meaningful market discovery or independent price accuracy. Some otherwise valid snapshots may contain optional comparisons that are stale, misaligned, rejected or unavailable. These qualifications must remain next to affected findings.

The currently supported deterministic comparison rules include:

- **Seven-day relative movement:** source-reported BTC, ETH and SOL rolling changes require available, time-aligned observations. The existing materiality rule requires SOL to differ from both BTC and ETH by at least 2 percentage points.
- **Cross-source price assurance:** overlapping, source-timestamp-aligned observations are compared within 300 seconds of the relevant observations and report time, with a maximum accepted absolute difference of 1% relative to the primary market-source price. This is a **quality check**, not by itself a material market finding or a same-time executable price.
- **Archived interval comparison:** aligned spot observations from an eligible earlier pinned snapshot, no more than 90 minutes earlier, may support a bounded two-point percentage change. They do not establish the price path or a sustained trend between observations.

These rules are narrowly defined by repository code. Missing, stale or incompatible values must not be backfilled, estimated or silently replaced by an attractive chart. A successful source check does not turn an independently rejected optional comparison into an admitted claim.

## Finding and uncertainty states

**Finding** means at least one qualified material market comparison is supported by the admitted source-bound evidence. Its exact figures, observation window, significance limits, uncertainty and proposed follow-up test belong with the finding. Optional source-assurance checks stay supporting evidence.

**Factual update** means the required source is usable but no market comparison satisfies the existing materiality and eligibility rules. It is not evidence that nothing happened, nor a licence to invent an important conclusion. It may present supported facts and state what further comparable data would be required.

**Inconclusive** means essential evidence identity, alignment, required quality or provenance cannot be established for a legitimately displayable assessment. A candidate rejected by the publication validator remains **unpublished**, not a successfully published inconclusive report. Absence of an optional cross-check alone does not make an otherwise validated report inconclusive.

A missing or incomparable observation is itself a limitation. Neither a source-consistency check nor a two-point movement proves causation, predictive power or future returns.

## Inspecting provenance and reproducing the record

The supporting-evidence links on a source-bound article identify the exact current and, where applicable, comparison JSON snapshots. The source path, Git commit, SHA-256 digest and observation wording allow a reviewer to compare the article with the archived bytes. For example, the Git command 'git show COMMIT:PATH' retrieves the committed source at that revision; the digest can be independently calculated over those bytes.

The **original archived Markdown** is linked separately at the site-build commit. The article's expandable technical record retains original report text, quality and source-status diagnostics, archived citation material and processing details. The repository contains the generator, validation code and reproduction tests. Generated '_site/' HTML is disposable output, not an additional evidence store.

A reproducible record makes a claim inspectable; it does not guarantee that an external source was accurate or that a historical model-generated interpretation was sound.

## Demo and non-advice boundary

CryptoPulse is an experimental publishing demonstration. Its reports and source material may be inaccurate, incomplete, stale, misleading, unsupported or hallucinated. This is **not financial advice, investment research, a recommendation or a trading signal**. Do not use it to make trading, investment or risk decisions. General limitations are explained here; material report-specific exceptions must remain visible beside the affected claims.
