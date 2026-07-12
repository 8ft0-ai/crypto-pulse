# Offline validation pipeline

> **Mode:** Reference  
> **Audience:** CryptoPulse developers and reviewers  
> **Outcome:** Look up the deterministic validation stages, command interface, outputs and exit behaviour used to accept or reject structured analysis.

The offline pipeline accepts an evidence bundle and a structured analysis object. It performs no provider call, uses no secret and has no network dependency.

## Implementation

| Responsibility | Module |
| --- | --- |
| Pipeline entry point | [`llm_analysis/pipeline.py`](../../llm_analysis/pipeline.py) |
| Schema validation | [`llm_analysis/schema_validation.py`](../../llm_analysis/schema_validation.py) |
| Contract and semantic validation | [`llm_analysis/validate.py`](../../llm_analysis/validate.py) |
| Deterministic rendering | [`llm_analysis/render.py`](../../llm_analysis/render.py) |
| Command entry point | [`llm_analysis/__main__.py`](../../llm_analysis/__main__.py) |

Canonical schemas:

- [`schemas/crypto-market-evidence-bundle-v1.json`](../../schemas/crypto-market-evidence-bundle-v1.json)
- [`schemas/crypto-market-analysis-v1.json`](../../schemas/crypto-market-analysis-v1.json)

## Inputs

```text
versioned evidence-bundle JSON
versioned structured-analysis JSON
reviewer-visible evidence and analysis schemas
```

## Accepted outputs

```text
byte-stable canonical analysis JSON
byte-stable repository-rendered Markdown
empty rejecting diagnostic set
```

## Rejected outputs

```text
ordered diagnostics grouped by validation stage
no normalised accepted analysis
no Markdown output
```

The command removes stale output paths when validation fails. A rejected run cannot leave an older normalised file or Markdown file appearing to represent the current inputs.

## Validation stages

### 1. Schema

The validator applies the checked-in Draft 2020-12 schema documents without fetching remote schemas.

Supported schema features include:

```text
local references
strict object properties
required properties
types
enumerations
constants
patterns
array limits
uniqueness
conditionals
allOf
oneOf
RFC 3339 date-time formats
```

A schema failure stops acceptance but remains associated with the schema stage.

### 2. Referential integrity

Checks include:

- evidence identifiers are unique;
- the analysis names the selected evidence bundle;
- every claim evidence reference exists;
- every quoted-value reference exists;
- both sides of a structured comparison exist.

### 3. Value consistency

Checks include:

- quoted numbers and units exactly match evidence;
- numbers in prose are traceable to referenced values, source-reason text, time-window field names or observation timestamps;
- timestamps match referenced evidence;
- known asset and source names have supporting evidence;
- capitalised named tokens absent from the bundle are rejected;
- percentage and US-dollar wording uses compatible units;
- structured comparison references appear on the claim;
- comparison units and declared direction match the evidence values.

### 4. Permitted semantics

The claim taxonomy imposes these evidence shapes:

| Claim type | Semantic requirement |
| --- | --- |
| `absolute_observation` | Restates compatible evidence without unsupported inference. |
| `directional_observation` | Uses numeric or explicitly directional status evidence. |
| `comparison` | Uses compatible numeric evidence and a valid comparison object. |
| `source_disagreement` | Compares the same measurement from different sources. |
| `data_quality_limitation` | Uses source, snapshot, status, reason, warning or coverage evidence. |
| `qualitative_interpretation` | Uses at least two evidence records and adds no structured number or comparison. |

The complete taxonomy is defined in [Governed analysis contract](governed-analysis-contract.md).

### 5. Policy

Sentence-aware policy checks reject:

- unsupported market causality;
- forecasts and future-direction claims;
- advice and recommendations;
- targets, support, resistance, entries and exits;
- trading signals and watchlists;
- position, exposure, allocation or portfolio actions;
- prompt or schema override attempts;
- disclaimer weakening;
- prohibited structured fields.

A source-status explanation, such as a provider being skipped after an HTTP failure, is not classified as market causality when it is supported only by source-quality evidence.

### 6. Deterministic rendering

[`llm_analysis/render.py`](../../llm_analysis/render.py) renders only accepted analysis.

Repository code owns:

- headings and section order;
- immutable product boundaries;
- evidence annotations;
- claim type and confidence labels;
- schema, prompt and evidence-bundle metadata;
- Markdown control-character escaping;
- whitespace normalisation.

Model-controlled strings cannot create headings, lists, links, HTML or other document structure. Identical accepted inputs produce identical canonical JSON and Markdown bytes.

## Command line

Run the pipeline against the checked-in valid fixtures:

```bash
python -m llm_analysis \
  tests/fixtures/llm_analysis/evidence_bundle_valid.json \
  tests/fixtures/llm_analysis/analysis_valid.json \
  --schemas-dir schemas \
  --normalised-output /tmp/analysis.normalised.json \
  --markdown-output /tmp/analysis.md
```

The command writes a stable JSON validation report to standard output.

| Exit status | Meaning |
| --- | --- |
| `0` | Input accepted and requested outputs written. |
| `2` | Input rejected; accepting outputs are absent or removed. |

## Fixture coverage

Fixtures are under [`tests/fixtures/llm_analysis/`](../../tests/fixtures/llm_analysis/README.md). Relevant tests include:

- [`tests/test_llm_analysis_contract.py`](../../tests/test_llm_analysis_contract.py)
- [`tests/test_llm_analysis_pipeline.py`](../../tests/test_llm_analysis_pipeline.py)
- [`tests/test_llm_analysis_dry_run.py`](../../tests/test_llm_analysis_dry_run.py)
- [`tests/test_llm_analysis_publication.py`](../../tests/test_llm_analysis_publication.py)

Invalid fixtures deliberately exercise schema, evidence-reference, value, semantic, policy and prompt-injection rejection paths.

## Boundary

The offline pipeline has:

```text
no provider client
no network access
no OPENROUTER_API_KEY requirement
no branch or workflow write operation
no model evaluation
no schedule
no model-authored Markdown
no committed _site output
```

For why acceptance is layered and fail-closed, see [Fail-closed analysis validation](../explanation/fail-closed-analysis-validation.md).
