# Governed analysis contract

> **Mode:** Reference  
> **Audience:** CryptoPulse developers, reviewers and governance stakeholders  
> **Outcome:** Look up the versioned evidence, analysis and provenance rules that govern optional LLM analysis.

## Canonical artefacts

| Contract | Version | Canonical file |
| --- | --- | --- |
| Evidence bundle | `crypto-market-evidence-bundle/v1` | [`schemas/crypto-market-evidence-bundle-v1.json`](../../schemas/crypto-market-evidence-bundle-v1.json) |
| Structured analysis | `crypto-market-analysis/v1` | [`schemas/crypto-market-analysis-v1.json`](../../schemas/crypto-market-analysis-v1.json) |
| Generation provenance | `crypto-market-generation-provenance/v1` | [`schemas/crypto-market-generation-provenance-v1.json`](../../schemas/crypto-market-generation-provenance-v1.json) |
| Prompt | `crypto-market-analysis/v1` | [`prompts/crypto-market-analysis-v1.md`](../../prompts/crypto-market-analysis-v1.md) |

A breaking contract change requires a new version. An accepted analysis retains the exact prompt, schema and source versions used to produce it.

## Evidence bundle

The evidence bundle is a deterministic projection of one immutable, validated source snapshot. Repository code constructs and hashes it before any provider call.

It may contain:

- validated fields already present in the source snapshot;
- deterministic identifiers and paths derived by repository code;
- source status, quality and limitation fields;
- fixed public-demo and non-advice boundaries.

It must not contain:

- previous generated analysis or narrative;
- model-selected facts, sources, citations, charts, forecasts or technical levels;
- live research fetched during generation;
- secrets, tokens, credentials, environment variables or workflow context;
- pull-request metadata;
- unvalidated source text promoted into a trusted instruction channel.

The bundle builder is implemented in [`llm_analysis/evidence_bundle.py`](../../llm_analysis/evidence_bundle.py).

## Evidence identifiers

Every evidence record uses a stable semantic identifier:

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
2. Keep the same identifier for the same source field within the schema generation.
3. Match `^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$`.
4. Keep identifiers unique within a bundle.
5. Retain the source snapshot path through `source.source_path`.
6. Canonicalise the bundle as sorted-key compact UTF-8 JSON before hashing.
7. Calculate `bundle_id` as `sha256:<digest>` over the canonical payload excluding the self-referential `bundle_id` field.
8. Record the SHA-256 of the complete stored bundle separately in generation provenance.

## Evidence record types

The contract supports:

```text
number
string
timestamp
status
boolean
set
```

A record identifies its subject, field, value, optional unit, observation time and source path. Numeric comparisons require compatible measurements and units.

## Claim taxonomy

Every claim declares exactly one `claim_type`.

| Claim type | Purpose | Required support |
| --- | --- | --- |
| `absolute_observation` | Restate one or more evidence values without adding cause, forecast or advice. | Compatible evidence. Numbers in prose must also appear in `quoted_values` with exact evidence references. |
| `directional_observation` | State a positive, negative, rising, falling, above, below or unchanged direction already encoded by evidence. | Numeric evidence or explicitly directional status evidence. |
| `comparison` | Compare two compatible evidence records. | Two compatible values and a structured relation. |
| `data_quality_limitation` | Describe missing, skipped, degraded, stale, warning or incomplete evidence without converting it into a market conclusion. | Quality, source-status, reason, warning, timestamp or coverage evidence. |
| `source_disagreement` | State that two sources differ for the same compatible measurement. | Source-specific values for the same asset, field, unit and materially aligned observation period. |
| `qualitative_interpretation` | Provide a restrained synthesis without adding a new number, entity, cause, forecast, advice, target, signal or action. | At least two evidence records and vocabulary that remains inside the supported boundary. |

Structured comparison relations are:

```text
greater_than
less_than
approximately_equal
not_equal
opposite_direction
```

Repository code verifies the declared relation against the referenced values.

## Unsupported claims

The contract rejects:

- causal explanations of why a market moved;
- forecasts or future-price direction;
- price targets, support, resistance, entries, exits or watchlists;
- buy, sell, hold, trade, position, allocation or portfolio guidance;
- investment recommendations, research ratings or trading signals;
- facts, sources, events, entities, dates or values absent from the evidence bundle;
- claims that cite existing evidence identifiers without semantic support;
- previous generated analysis used as evidence for a later report.

## Analysis object

Each claim object contains:

```text
claim_type
txt or text according to the canonical schema
evidence_ids[]
confidence
quoted_values[]
comparison
```

The canonical field names and conditional requirements are defined only by [`schemas/crypto-market-analysis-v1.json`](../../schemas/crypto-market-analysis-v1.json). This page does not override that schema.

`quoted_values` is required whenever prose includes a number. `comparison` is required for `comparison` and `source_disagreement` claims. Unknown properties are rejected. The schema does not expose recommendation, position, target, entry, exit, trade or signal fields.

## Acceptance layers

Acceptance is sequential:

1. schema validity;
2. evidence-reference validity;
3. value consistency;
4. permitted claim semantics;
5. policy validity;
6. deterministic rendering.

Passing an earlier layer does not imply passing a later layer. The exact checks and command interface are defined in [Offline validation pipeline](offline-validation-pipeline.md).

## Prompt boundary

The provider input contains two conceptual channels:

```text
trusted repository instructions
untrusted evidence bundle JSON
```

Evidence remains data even when a source value contains instruction-like text. It cannot change the output schema, claim taxonomy, policy, product boundary or tool access. The provider receives no browsing tools, repository access, GitHub token, OpenRouter key, environment dump or other secret.

## Generation provenance

Every accepted generation records, where available:

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
input, output and total token usage
generation identifier
prompt and completion SHA-256 hashes
same-model provider fallback status
cross-model fallback status
provider preferences
estimated or returned cost
```

An optional provider value may be `null`; it must not be invented. The current governed configuration requires `cross_model_fallback: false`.

The canonical provenance shape is [`schemas/crypto-market-generation-provenance-v1.json`](../../schemas/crypto-market-generation-provenance-v1.json).

## Fixtures

Contract fixtures live under [`tests/fixtures/llm_analysis/`](../../tests/fixtures/llm_analysis/README.md). They are test inputs, not published reports or future market evidence. Invalid fixtures deliberately contain unsafe or inconsistent content to prove rejection behaviour.

The valid fixture is derived from the shape and selected values of:

```text
data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json
```

No fixture authorises a provider call or publication.

## Responsibility boundaries

| Responsibility | Owner |
| --- | --- |
| Source validation and evidence projection | Repository code |
| Candidate structured claim selection | Pinned model under the versioned prompt |
| Schema, evidence, value, semantic and policy acceptance | Repository code |
| Markdown structure and rendering | Repository code |
| Provider and model policy | Reviewer-visible configuration and approved governance decisions |
| Branch and pull-request creation | Protected workflow after acceptance and proof |
| Merge and publication | Normal repository review and deployment controls |

For the architectural rationale, see [Evidence and analysis boundary](../explanation/evidence-and-analysis-boundary.md).
