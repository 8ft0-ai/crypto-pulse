# Simplifying the semantic claim-plan pipeline

> **Status:** Working note, not an approved specification or implementation plan.
>
> **Context:** Architectural reflection following the prompt-v2 corrective semantic-model screen.

## Assessment

The current contract asks the LLM to do too many different kinds of work in one generation.

It is simultaneously interpreting heterogeneous evidence, assigning semantic intent, discovering valid claim boundaries, determining comparison compatibility and operand cardinality, distinguishing source status from data quality, selecting material information, assigning sections and ordering, and emitting a complex nested object whose full rules cannot be expressed by JSON Schema.

That makes the model behave as a **semantic compiler**. The failures observed so far are compiler-style failures: wrong cardinality, wrong intent, invalid grouping, hidden invariants and unsupported combinations.

Structured output helps with syntax, but schema adherence does not guarantee semantic correctness. The process should therefore be decomposed so deterministic repository code owns formal correctness and the model is used only where judgement adds value.

## Main simplification

The repository should construct every semantically valid claim candidate. The LLM should only choose among them.

Instead of asking the model to construct a claim:

```json
{
  "intent": "comparison",
  "evidence_ids": ["...", "..."],
  "comparison_relation": "greater_than",
  "section": "market_snapshot"
}
```

The repository would generate a complete candidate:

```json
{
  "candidate_id": "claim-017",
  "intent": "comparison",
  "evidence_ids": [
    "market.coingecko.btc.price_usd",
    "exchange.coinbase.btc-usd.price"
  ],
  "comparison_relation": "not_equal",
  "section": "market_snapshot",
  "subject": "btc",
  "features": {
    "cross_source": true,
    "difference_class": "minor",
    "redundancy_group": "btc_spot_price"
  }
}
```

The model would return only:

```json
{
  "selected_candidate_ids": [
    "claim-017",
    "claim-004",
    "claim-029"
  ]
}
```

Optionally it could provide bounded priority:

```json
{
  "selections": [
    {"candidate_id": "claim-017", "priority": 1},
    {"candidate_id": "claim-004", "priority": 2}
  ]
}
```

This changes the model’s role from **semantic construction** to **editorial selection**.

## Proposed ownership split

| Responsibility | Better owner |
| --- | --- |
| Field and measure normalisation | Repository |
| Valid absolute and directional claims | Repository |
| Compatible comparison pairs | Repository |
| Comparison relation from numeric values | Repository |
| One-source status boundaries | Repository |
| Explicit data-quality eligibility | Repository |
| Evidence identifiers | Repository-generated candidate |
| Section eligibility | Repository |
| Materiality and usefulness | Model or deterministic ranker |
| Final ordering | Model or repository |
| Rendering and exact values | Repository |

Most rules that have caused failures are deterministic. There is little value in asking an LLM to rediscover them.

## Proposed pipeline

```text
raw evidence
    ↓
canonical evidence normalisation
    ↓
deterministic claim-candidate compiler
    ↓
deterministic filtering and feature calculation
    ↓
LLM selects candidate IDs
    ↓
small selection validator
    ↓
optional bounded repair
    ↓
deterministic ordering and rendering
```

### Deterministic candidate compiler

The compiler can enumerate:

- one absolute candidate for each eligible numeric observation;
- one directional candidate for each eligible change record;
- one comparison candidate for each compatible pair;
- one source-status candidate for each source subject;
- one data-quality candidate for each explicitly missing, failed, stale, degraded, incomplete or conflicting record;
- supported snapshot-status candidates.

This makes invalid constructs unreachable:

- comparisons cannot have more than two operands;
- incompatible measures are never offered;
- source subjects cannot be mixed;
- routine coverage metadata cannot become a quality limitation;
- invented intents cannot appear.

### Precomputed editorial features

Each candidate can carry repository-calculated signals such as subject, metric, section, source count, cross-source status, direction, magnitude bucket, recency, quality status, conflict status, novelty and redundancy group.

The model can then answer a much more natural question:

> Which small set of valid observations is most useful for the reader?

### Deterministic baseline

Before using an LLM, build a rule-based selector that scores candidates using:

```text
explicit conflict
material movement
cross-source corroboration
data-quality significance
subject diversity
section coverage
recency
redundancy penalty
```

This creates a meaningful baseline. The LLM must measurably outperform it rather than merely produce a valid result.

## Structural groundedness

Groundedness should be a property of the pipeline:

```text
evidence → validated candidate → selected candidate ID
```

The model never writes evidence identifiers, numeric values, comparison relations, intents, source subjects or field names. It therefore cannot create an unsupported claim. The existing canonical validator can remain as defence in depth.

## Recommended artefacts

### Repository-owned claim candidate

```json
{
  "candidate_id": "claim-017",
  "intent": "comparison",
  "evidence_ids": ["e1", "e2"],
  "comparison_relation": "not_equal",
  "section": "market_snapshot",
  "subject": "btc",
  "features": {
    "materiality": "medium",
    "cross_source": true,
    "redundancy_group": "btc_spot_price"
  }
}
```

### Model-owned selection

```json
{
  "selected_candidate_ids": [
    "claim-017",
    "claim-029",
    "claim-006"
  ]
}
```

### Repository-reconstructed canonical plan

```json
{
  "claim_plan_version": "...",
  "evidence_bundle_id": "...",
  "analysis_order": ["market_snapshot", "data_quality"],
  "sections": []
}
```

## Evaluation impact

The evaluation would focus on:

1. **Candidate recall:** Did the compiler generate every valid useful claim?
2. **Selection precision:** How many selected candidates were useful?
3. **Selection recall:** Did the selector choose the important candidates?
4. **Redundancy:** Did it choose overlapping candidates?
5. **Stability:** Does it make similar selections across repeats?
6. **Incremental value:** Does it outperform the deterministic ranker?

Schema validity and evidence groundedness should approach 100% by construction and no longer dominate model evaluation.

## Recommendation

Pause further prompt-version work and the pending Sol/Nex paid calibration.

The next repository slice should be:

> **Compile valid claim candidates deterministically and reduce the LLM role to bounded candidate selection.**

Build a no-LLM ranking baseline first. Then compare GPT-5.6 Luna and possibly Nex using the small selection contract on the existing corpus.

This is not giving up on the model. It places the model where it can add genuine value: deciding what is interesting rather than reproducing rules the repository already knows.

See [Implementation patterns and references](semantic-claim-selection-implementation-patterns.md) for tool calling, retries, post-processing and related approaches.
