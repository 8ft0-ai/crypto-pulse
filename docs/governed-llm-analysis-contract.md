# Governed LLM analysis contract v1

Status: Phase 5 contract for issue #183.

This document defines the first governed interface between an immutable CryptoPulse source snapshot, an optional LLM analysis call, deterministic repository validation, and deterministic report rendering. It is a contract, not a provider integration or publication workflow.

## Versioned artefacts

```text
Evidence bundle schema:  crypto-market-evidence-bundle/v1
Analysis schema:         crypto-market-analysis/v1
Provenance schema:       crypto-market-generation-provenance/v1
Prompt version:          crypto-market-analysis/v1
```

The reviewer-visible files are:

```text
schemas/crypto-market-evidence-bundle-v1.json
schemas/crypto-market-analysis-v1.json
schemas/crypto-market-generation-provenance-v1.json
prompts/crypto-market-analysis-v1.md
```

A breaking change requires a new version. Existing accepted analysis must retain the exact schema and prompt versions used to produce it.

## Evidence bundle boundary

The evidence bundle is a compact deterministic projection of one immutable, validated source snapshot. It may contain only:

- validated fields already present in the selected source snapshot;
- deterministic identifiers and paths derived by repository code;
- source quality and source-status fields required to explain evidence limitations;
- canonical public-demo and non-advice product boundaries.

It must not contain:

- previous LLM analysis or generated narrative;
- model-selected facts, sources, citations, charts, forecasts, or technical levels;
- live web research or data fetched during the LLM step;
- secrets, tokens, workflow context, environment variables, repository credentials, or pull-request metadata;
- unvalidated free-form content promoted into a trusted instruction channel.

Repository code constructs and hashes the bundle before the provider call. The model cannot add, delete, rename, or reinterpret evidence records.

## Deterministic evidence IDs

Every evidence item has a stable semantic identifier:

```text
<namespace>.<entity_type>.<stable_entity_key>.<field>
```

Examples:

```text
market.asset.bitcoin.price_usd
market.asset.bitcoin.change_24h_pct
exchange.coinbase_exchange.btc-usd.price
quality.snapshot.status
source.binance.status
source.binance.reason
```

Rules:

1. Use lower-case stable source and entity keys, not display names or array positions.
2. Preserve the same ID for the same source field in the same schema generation.
3. An ID must match `^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$`.
4. IDs must be unique within a bundle.
5. Every evidence record retains its source snapshot path through `source.source_path`.
6. The bundle is canonicalised using sorted-key compact UTF-8 JSON before SHA-256 hashing.
7. The top-level `bundle_id` is `sha256:<digest>` for the canonical bundle payload as defined by the future builder implementation. The builder must document whether the `bundle_id` field itself is excluded from that digest to avoid self-reference.

## Evidence types

The first contract supports:

```text
number
string
timestamp
status
boolean
set
```

A record also identifies its subject, field, value, optional unit, observation time, and source path. Numeric comparisons are valid only when both referenced records have compatible meaning and units.

## Supported claim taxonomy

Every generated claim must declare exactly one supported `claim_type`.

### `absolute_observation`

Restates one or more evidence values without adding a cause, forecast, recommendation, or unreferenced fact.

Permitted support: any compatible evidence type. Numbers appearing in text must also appear in `quoted_values` with an exact evidence reference.

### `directional_observation`

States an observed positive, negative, rising, falling, above, below, or unchanged direction already encoded by numeric or status evidence.

Permitted support: numeric evidence or an explicitly directional status field. The model may not infer a future direction.

### `comparison`

Compares two compatible evidence records using one declared structured relation:

```text
greater_than
less_than
approximately_equal
not_equal
opposite_direction
```

Permitted support: normally two numeric values with compatible units and time windows. Repository code must verify the declared relation.

### `data_quality_limitation`

Explains missing, skipped, degraded, stale, warning, or incomplete source evidence without converting that limitation into a market conclusion.

Permitted support: quality, source-status, reason, warning, timestamp, or coverage evidence.

### `source_disagreement`

States that two sources differ for the same compatible measurement. The structured comparison identifies the two source values.

Permitted support: two source-specific values for the same asset, field, unit, and materially aligned observation period. Repository code defines any tolerance used to decide whether a disagreement is meaningful.

### `qualitative_interpretation`

Provides a restrained synthesis of at least two evidence records where the interpretation introduces no new number, named entity, cause, forecast, advice, target, signal, or portfolio action.

This is the narrowest and highest-risk class. It must fail closed when deterministic validation cannot establish that its terms remain inside the supported vocabulary and evidence boundary.

## Unsupported claims

The initial contract does not support:

- causal explanations of why a market moved;
- forecasts or future-price direction;
- price targets, support/resistance, entries, exits, or watchlists;
- buy, sell, hold, trade, position, allocation, or portfolio guidance;
- investment recommendations, research ratings, or trading signals;
- facts, sources, events, entities, dates, or values absent from the evidence bundle;
- a claim that cites an existing evidence ID but is not semantically supported by that evidence type;
- prior generated analysis as evidence for a later report.

## Analysis object rules

The structured analysis schema provides constrained report slots. Each claim object includes:

```text
claim_type
text
evidence_ids[]
confidence
quoted_values[]     # required whenever the prose quotes a number
comparison          # required for comparison and source_disagreement
```

The schema does not expose fields named `recommendation`, `position`, `target`, `entry`, `exit`, `trade`, or `signal`. Unknown properties are rejected.

Validation is deliberately layered:

1. **Schema validity** — the JSON shape and declared fields are valid.
2. **Referential validity** — every evidence ID exists in the selected bundle.
3. **Value consistency** — quoted numbers, dates, entities, units, and comparison direction match referenced evidence.
4. **Permitted claim semantics** — the declared claim class is supported by the referenced evidence types.
5. **Policy validity** — the output contains no causality, forecast, advice, recommendation, target, signal, position guidance, prompt override, or disclaimer weakening.

Passing an earlier layer never implies passing a later one.

## Prompt trust boundary

The prompt has two conceptual channels:

```text
trusted repository instructions
untrusted evidence bundle JSON
```

The evidence payload is data, even when a source field contains instruction-like text. Source text cannot:

- alter the output schema or claim taxonomy;
- weaken policy or product boundaries;
- request tools, browsing, secrets, or repository access;
- replace the system/task instructions;
- instruct the model to emit Markdown or non-JSON output.

The provider receives only the versioned prompt and curated evidence bundle. It receives no OpenRouter key, GitHub token, environment dump, workflow context, or repository secret.

## Provenance contract

Each accepted generation records:

```text
requested model
actual model
actual provider
prompt version
analysis schema version
evidence schema version
source snapshot path and SHA-256
evidence bundle ID and SHA-256
generation timestamp
temperature and output-token limit
input, output, and total token usage
generation identifier
prompt and completion SHA-256 hashes
provider fallback status
cross-model fallback status
provider preferences
estimated cost where available
```

A missing optional provider field may be recorded as `null`; it must not be invented. The initial production-proof configuration must record `cross_model_fallback_used: false`.

## Fixture policy

Fixtures under `tests/fixtures/llm_analysis/` are contract examples, not published market reports and not future market evidence. Invalid fixtures deliberately contain unsafe or inconsistent content so later validators can prove fail-closed behaviour.

The valid fixture is based on the shape and selected values of:

```text
data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json
```

No fixture authorises publication or provider calls.

## Boundaries preserved

- Existing deterministic report generation remains independent of these contracts.
- No OpenRouter API call is introduced.
- No GitHub Actions workflow is introduced.
- No report branch or pull request is generated by these contracts.
- No LLM-authored Markdown is accepted as report source.
- No generated `_site/` output is committed.
