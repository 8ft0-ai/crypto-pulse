# Offline governed-analysis pipeline

Status: implementation record for issue #184.

This pipeline is the deterministic boundary between a validated CryptoPulse evidence bundle and any Markdown that may later be reviewed for publication. It performs no provider call, uses no secret, and has no network dependency.

## Inputs and outputs

Inputs:

```text
versioned evidence-bundle JSON
versioned structured-analysis JSON
reviewer-visible evidence and analysis JSON Schemas
```

Accepted outputs:

```text
byte-stable canonical analysis JSON
byte-stable repository-rendered Markdown
empty diagnostic set
```

Rejected outputs:

```text
ordered diagnostics grouped by validation stage
no normalised analysis
no Markdown
```

The command-line interface removes any stale output paths when validation fails. An invalid run therefore cannot leave an older Markdown file looking like the result of the current input.

## Validation stages

Validation always reports the stage that owns a failure. Passing one stage does not imply that a later stage will pass.

### 1. Schema

`llm_analysis/schema_validation.py` validates the supplied objects from the checked-in Draft 2020-12 schema documents. The offline validator implements the schema keywords used by the Phase 5 contracts, including local references, strict object properties, required properties, types, enumerations, constants, patterns, array limits, uniqueness, conditionals, `allOf`, `oneOf`, and RFC 3339 date-time formats.

This avoids fetching remote schemas or introducing a network-time dependency.

### 2. Referential

The validator checks that:

- evidence IDs are unique;
- the analysis identifies the selected bundle;
- every claim evidence reference exists;
- every quoted-value reference exists;
- both sides of a structured comparison exist.

### 3. Value consistency

The validator checks that:

- quoted numbers and units exactly match evidence;
- numbers stated in prose are traceable to referenced values, source-reason text, time-window field names, or observation timestamps;
- timestamps match referenced evidence;
- known asset and source names are attached to supporting evidence;
- capitalised named tokens absent from the bundle are rejected;
- percentage and US-dollar wording is backed by compatible units;
- structured comparison references appear on the claim;
- comparison units and declared direction match the evidence values.

### 4. Permitted semantics

Each claim type has a bounded evidence shape:

- directional observations require numeric or directional-status evidence;
- comparisons require compatible numeric evidence and a comparison object;
- source disagreements must compare the same measurement from different sources;
- data-quality limitations require source, snapshot, status, reason, warning, or coverage evidence;
- qualitative interpretations require at least two evidence records and cannot add structured numbers or comparisons.

### 5. Policy

Sentence-aware policy rules reject:

- unsupported market causality;
- forecasts and future-direction claims;
- advice and recommendations;
- targets, support, resistance, entries, and exits;
- trading signals and watchlists;
- position, exposure, allocation, or portfolio actions;
- prompt or schema override attempts;
- disclaimer weakening;
- prohibited structured fields.

A source-failure explanation such as a provider being skipped because an HTTP request failed is not treated as market causality when it is backed only by source-quality evidence.

## Prompt-injection boundary

Evidence values remain data even when they contain instruction-like text. The validator does not interpret source strings as commands. Analysis that repeats or obeys an override instruction is rejected by policy validation.

The renderer also collapses model-controlled whitespace and escapes Markdown control characters. A generated string cannot create headings, lists, links, HTML, or other document structure. Repository code owns all headings, sections, evidence annotations, boundaries, and metadata.

## Deterministic rendering

`llm_analysis/render.py` renders only a valid analysis. Its output includes:

- the headline and its claim metadata;
- immutable product boundaries from the evidence bundle;
- fixed report sections;
- claim type, confidence, and evidence IDs for every rendered claim;
- evidence-bundle, schema, and prompt versions.

Identical accepted inputs produce identical canonical JSON and Markdown bytes.

## Command-line use

```bash
python -m llm_analysis \
  tests/fixtures/llm_analysis/evidence_bundle_valid.json \
  tests/fixtures/llm_analysis/analysis_valid.json \
  --schemas-dir schemas \
  --normalised-output /tmp/analysis.normalised.json \
  --markdown-output /tmp/analysis.md
```

The command prints a stable JSON validation report. Exit status is `0` for accepted input and `2` for rejected input.

## Preserved boundaries

```text
No OpenRouter client.
No network access.
No OPENROUTER_API_KEY requirement.
No workflow or branch automation.
No model evaluation.
No scheduled generation.
No LLM-authored Markdown.
No committed _site output.
```
