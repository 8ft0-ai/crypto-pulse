# Semantic claim-plan contract

> **Mode:** Reference  
> **Audience:** CryptoPulse developers, reviewers and governance stakeholders  
> **Outcome:** Look up the versioned semantic-plan shape and the boundary between model selection and deterministic rendering.

## Canonical artefacts

| Contract | Version | Canonical file |
| --- | --- | --- |
| Semantic claim plan | `crypto-market-claim-plan/v1` | [`schemas/crypto-market-claim-plan-v1.json`](../../schemas/crypto-market-claim-plan-v1.json) |
| Semantic planning prompt | `crypto-market-claim-plan/v1` | [`prompts/crypto-market-claim-plan-v1.md`](../../prompts/crypto-market-claim-plan-v1.md) |
| Evidence bundle | `crypto-market-evidence-bundle/v1` | [`schemas/crypto-market-evidence-bundle-v1.json`](../../schemas/crypto-market-evidence-bundle-v1.json) |

The existing model-authored structured-analysis contract remains historical and independently valid. The semantic plan is a separate versioned provider contract and does not rewrite earlier evaluation evidence.

## Responsibility boundary

```text
Governed evidence bundle
        ↓
LLM semantic claim plan
        ↓
Fail-closed claim-plan validation
        ↓
Repository-owned deterministic renderer
```

The model may select salient evidence, omit unhelpful evidence, group and order claims, choose a bounded intent, identify a bounded comparison relation and return bounded confidence.

Repository code owns evidence lookup, values, signs, directions, units, currencies, precision, rounding, approximation wording, dates, timestamps, symbols, names, labels, aliases, headings, final sentences, limitation wording, disclaimers, validation, rendering and publication eligibility.

## Root shape

```text
claim_plan_version
prompt_version
evidence_bundle_id
analysis_order[]
sections[]
  section_kind
  claims[]
    claim_id
    intent
    evidence_ids[]
    comparison_relation
    confidence
```

`analysis_order` contains section kinds rather than model-authored headings. Each declared section must later be reconciled with this order by the semantic validator.

## Section kinds

```text
market_summary
key_observations
risks_and_limitations
data_quality
source_status
```

These are stable repository section identifiers. They are not final rendered headings.

## Claim intents

| Intent | Semantic responsibility |
| --- | --- |
| `absolute_observation` | Select one or more evidence records for an exact repository-rendered observation. |
| `directional_observation` | Select evidence that already encodes a supported direction. |
| `comparison` | Select compatible operands and one bounded relation. |
| `source_status` | Select evidence describing a source state. |
| `data_quality_limitation` | Select explicit missing, failed, stale, degraded, skipped, warning, incomplete or conflicting evidence. |
| `snapshot_status` | Select snapshot-quality or snapshot-status evidence. |

No intent permits cause, forecast, advice, target, signal or action.

## Comparison relations

```text
none
greater_than
less_than
approximately_equal
not_equal
opposite_direction
```

`comparison_relation` is required for every claim so the provider schema has no optional object property. Non-comparison claims must use `none`; comparison claims must use a compatible non-`none` relation. The canonical semantic validator enforces that relationship after provider generation.

## Confidence

```text
high
medium
low
```

Confidence is a bounded plan attribute. It cannot add prose or weaken evidence compatibility.

## Prohibited model-owned content

The contract has no field for:

- report prose, headlines, headings, sentences or Markdown;
- copied numeric or string values;
- signs, units, currencies, precision or rounding;
- dates, timestamps, labels or aliases;
- explanation, cause, forecast, advice, target, signal, position or action;
- publication or policy decisions.

Unknown and additional properties fail schema validation. Evidence identifiers are references only; repository code resolves their values.

## Provider projection

The canonical schema uses strict objects and `uniqueItems` checks. [`llm_analysis/openai_schema_projection.py`](../../llm_analysis/openai_schema_projection.py) creates a deterministic provider-only projection by removing unsupported metadata and keywords such as `uniqueItems`, while preserving the unchanged canonical schema for offline validation.

All object properties are required. The projection therefore needs no nullable placeholder for the semantic-plan contract. The canonical schema remains authoritative.

## Fixtures

- [`claim_plan_valid.json`](../../tests/fixtures/llm_analysis/claim_plan_valid.json) exercises every intent and a bounded comparison.
- [`claim_plan_invalid_cases.json`](../../tests/fixtures/llm_analysis/claim_plan_invalid_cases.json) proves that prose, copied values, dates, unknown fields, unsupported enums, duplicate references and missing fields fail closed.

Fixtures authorise no provider call, publication or market-content merge.
