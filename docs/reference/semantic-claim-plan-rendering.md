# Semantic claim-plan rendering

> **Mode:** Reference  
> **Audience:** CryptoPulse developers, reviewers and governance stakeholders  
> **Outcome:** Look up the deterministic formatting, template and fail-closed rules applied after semantic-plan validation.

## Canonical implementation

| Artefact | Version or path |
| --- | --- |
| Renderer version | `crypto-market-claim-plan-renderer/v1` |
| Implementation | [`llm_analysis/claim_plan_render.py`](../../llm_analysis/claim_plan_render.py) |
| Claim-plan contract | [`schemas/crypto-market-claim-plan-v1.json`](../../schemas/crypto-market-claim-plan-v1.json) |
| Claim-plan validator | [`llm_analysis/claim_plan_validation.py`](../../llm_analysis/claim_plan_validation.py) |
| Golden output | [`tests/fixtures/llm_analysis/claim_plan_valid_rendered.md`](../../tests/fixtures/llm_analysis/claim_plan_valid_rendered.md) |

The renderer accepts only a claim plan that has already passed the canonical schema, referential, semantic and policy validator. A failed validation report produces no rendered output.

## Ownership boundary

The semantic plan contributes only:

- section ordering;
- claim ordering;
- bounded intent;
- evidence identifiers;
- bounded comparison relation;
- bounded confidence.

Repository code contributes:

- evidence lookup;
- numeric values and signs;
- direction wording;
- units and currency notation;
- precision, rounding and approximation wording;
- dates and timestamps;
- subject, source and metric labels;
- headings and final sentence templates;
- product boundaries;
- limitation and status wording;
- structured claim-to-evidence grounding.

No model-authored sentence, heading, label, value or date is interpolated.

## Numeric policy

| Unit | Display policy | Rounded-value policy |
| --- | --- | --- |
| `usd` | `US$`, thousands separators, maximum two decimal places | Half-up to two decimal places and prefix `approximately` when the displayed value differs from evidence |
| `percent` | Signed for absolute values; magnitude plus repository-owned direction wording for directional observations | Half-up to two decimal places and prefix `approximately` when the displayed value differs from evidence |
| `rank` | Integer prefixed with `#` | Non-integral evidence fails closed; rank is never rounded silently |

Unsupported units fail with `unsupported_unit`.

## Direction policy

Direction is derived from change-like numeric evidence, never selected as free-form text:

- positive — `increased by`;
- negative — `decreased by`;
- zero — `was unchanged at`.

The horizon is resolved from a bounded field mapping such as `change_24h_pct` → `over 24 hours`. Unknown directional fields fail closed.

## Timestamp policy

UTC `Z` timestamps preserve their supplied fractional precision and render as:

```text
YYYY-MM-DD HH:MM:SS[.fraction] UTC
```

Other timezone-aware RFC 3339 timestamps are normalised to UTC. Missing or invalid timezones fail closed.

## Alias and label policy

- subject display uses a source-controlled `name` or `symbol` from evidence;
- snapshot claims use the fixed label `the source snapshot`;
- source-reference display uses a bounded repository mapping;
- evidence fields use a bounded repository metric-label mapping;
- no subject identifier, source key or field name is silently converted into display text.

Missing aliases, source labels or metric mappings fail closed.

## Sentence templates

Each supported intent has a repository-owned template family:

- `absolute_observation` — exact evidence value or status;
- `directional_observation` — sign-derived direction and bounded horizon;
- `comparison` — compatible values and bounded relation;
- `source_status` — one source status plus supported recorded details;
- `data_quality_limitation` — explicit source or snapshot limitation wording;
- `snapshot_status` — fixed snapshot-status wording.

Same-measure/different-source `not_equal` comparisons use a dedicated source-disagreement template. No cause or market explanation is inferred.

## Grounding without lexical reparsing

`render_claim_plan` returns both byte-stable Markdown and a tuple of structured `RenderedClaim` records. Each record preserves:

```text
claim_id
intent
evidence_ids[]
repository-generated sentence
```

Review and provenance code can therefore establish grounding directly from the validated plan and evidence identifiers. It does not need to extract values or entities back out of final prose.

## Fail-closed conditions

Rendering stops on:

- an invalid validation report;
- unknown intent, relation or section;
- missing evidence;
- unsupported unit, metric or directional field;
- absent subject or source alias;
- invalid numeric, status, timestamp, Boolean or set evidence;
- unsupported claim cardinality;
- a missing or empty section.

The renderer performs no repair, fallback, provider call, publication or repository write.
