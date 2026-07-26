# Simplifying semantic claim selection

Status: exploratory architecture note. This is not yet an approved contract or implementation plan.

## Context

The current semantic claim-plan contract asks the LLM to do too many different kinds of work in one generation.

It is not merely selecting useful observations. It is simultaneously:

- interpreting heterogeneous evidence;
- deciding which semantic intent applies;
- discovering valid claim boundaries;
- determining comparison compatibility and operand cardinality;
- distinguishing source status from data quality;
- selecting material information;
- assigning sections and ordering;
- emitting a relatively complex nested object;
- satisfying rules that JSON Schema cannot fully express.

That is effectively asking the model to behave as a **semantic compiler**. The failures observed during evaluation are compiler-style errors rather than ordinary hallucinations: wrong cardinality, wrong intent, invalid grouping, hidden invariants and unsupported combinations.

Structured output does not solve this class of problem by itself. OpenAI distinguishes schema adherence from correctness, notes that structured outputs can still contain mistakes, and recommends examples or splitting complex tasks into simpler subtasks. Research evaluating constrained decoding similarly finds that syntactic validity does not guarantee good semantic output, particularly with complex real-world schemas.

## Main simplification

The repository should construct every semantically valid claim candidate. The LLM should only choose among them.

Instead of asking the model to produce this:

```json
{
  "intent": "comparison",
  "evidence_ids": ["...", "..."],
  "comparison_relation": "greater_than",
  "section": "market_snapshot"
}
```

The repository would first generate a valid candidate:

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
  "materiality_features": {
    "cross_source": true,
    "difference_class": "minor"
  }
}
```

The model would return only something like:

```json
{
  "selected_candidate_ids": [
    "claim-017",
    "claim-004",
    "claim-029"
  ]
}
```

It could optionally provide a bounded priority or ordering:

```json
{
  "selections": [
    {"candidate_id": "claim-017", "priority": 1},
    {"candidate_id": "claim-004", "priority": 2}
  ]
}
```

This changes the model's job from **semantic construction** to **editorial selection**.

## Proposed ownership split

| Responsibility | Current owner | Better owner |
| --- | --- | --- |
| Field and measure normalisation | Repository | Repository |
| Valid absolute claims | Model | Repository |
| Valid directional claims | Model | Repository |
| Compatible comparison pairs | Model | Repository |
| Comparison relation from numeric values | Model | Repository |
| One-source status boundaries | Model | Repository |
| Explicit data-quality eligibility | Model | Repository |
| Evidence identifiers | Model copies them | Repository-generated candidate |
| Section eligibility | Model | Repository |
| Materiality and usefulness | Model | Model or deterministic ranker |
| Final claim ordering | Model | Model or repository |
| Rendering and exact values | Repository | Repository |

Most of the rules that have caused failures are entirely deterministic. There is little value in asking an LLM to rediscover them.

## Better pipeline

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

### 1. Compile valid candidates deterministically

The candidate compiler can enumerate:

- one absolute candidate for each eligible numeric observation;
- one directional candidate for each eligible change record;
- one comparison candidate for each compatible pair;
- one source-status candidate for each source subject;
- one data-quality candidate for each record explicitly marked missing, failed, stale, degraded, incomplete, conflicting or similar;
- any snapshot-status candidates permitted by the repository rules.

Invalid constructs then become impossible:

- a comparison can never have four operands;
- incompatible measures are never offered;
- source subjects cannot be mixed;
- coverage metadata cannot become a data-quality limitation unless repository rules say it qualifies;
- invented intents cannot appear.

This follows the same broad architectural principle used in constrained semantic systems such as text-to-SQL: systems such as PICARD reject invalid continuations using a parser rather than expecting the model to learn every formal constraint from prose.

### 2. Calculate useful features before the LLM call

Each candidate can include repository-calculated signals such as:

```text
subject
metric
section
source count
cross-source status
direction
magnitude bucket
recency
quality status
conflict status
novelty
mandatory / optional
```

Do not provide model-authored numeric descriptions. Give the model bounded categorical features such as `large_movement`, `cross_source_difference` or `explicit_quality_warning`.

The model can then answer a more natural question:

> Which six of these valid observations are most useful for the reader?

That is a task LLMs are much better suited to.

### 3. Establish a deterministic baseline before using any LLM

The first version may not need a model at all.

A rule-based selector could score candidates using:

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

It could then select the highest-ranked non-duplicative candidates.

This creates a strong baseline. Any model must measurably outperform it rather than merely produce a valid result.

Traditional data-to-text work commonly separates content selection and planning from final realisation, rather than expecting one end-to-end generation to make every decision. CryptoPulse already has deterministic realisation, so moving claim construction into the repository is a natural continuation of that architecture.

## Use a tool call rather than a large response object

The remaining model interaction can be represented as a single forced tool:

```text
select_claims(
    selected_candidate_ids: array[candidate_id],
    maximum 8,
    unique items
)
```

OpenAI recommends function calling when the model is interacting with data or functionality in an application, rather than using a response schema merely to structure a user-facing response. Anthropic similarly supports forcing a specific tool call and recommends detailed parameter descriptions and validated input examples for complex inputs.

The candidate IDs can be represented as an enum for small candidate sets. For larger sets, validate them against a supplied lookup table after generation.

The tool description should state only the editorial criteria:

```text
Select the smallest set of materially useful, non-redundant
claim candidates for the report.

Prefer:
- material market movement;
- meaningful cross-source differences;
- explicit data-quality limitations;
- diversity across important subjects.

Do not select:
- routine successful source statuses unless needed;
- duplicate observations;
- an absolute observation already adequately represented
  by a selected comparison.
```

That is much easier than restating the full semantic validator.

## Make groundedness structural

CryptoPulse already has better grounding machinery than most retrieval-augmented generation systems because every observation refers to canonical evidence.

The safest path is:

```text
evidence → validated candidate → selected candidate ID
```

The model never writes:

- an evidence ID;
- a numeric value;
- a comparison relation;
- an intent;
- a source subject;
- a field name.

It therefore cannot create an unsupported claim. Groundedness becomes a property of the candidate compiler rather than an LLM evaluation score.

An LLM-based groundedness judge could still be used diagnostically, but it should not be the authority where exact deterministic checks are possible.

## Retries after simplification

A bounded validator-feedback loop is useful:

```text
attempt 1
    ↓
validate selected IDs and selection rules
    ↓
return exact machine-readable errors
    ↓
attempt 2
    ↓
accept or fail closed
```

For example:

```json
{
  "errors": [
    {
      "code": "too_many_candidates",
      "maximum": 8,
      "actual": 11
    },
    {
      "code": "duplicate_subject_metric",
      "candidate_ids": ["claim-017", "claim-021"]
    }
  ]
}
```

Libraries such as Instructor and Pydantic AI use this pattern: validate structured outputs, reflect validation failures back to the model and retry under an explicit attempt budget. Research on iterative refinement also shows that feedback and revision can improve first-pass results, although in CryptoPulse the feedback should come from deterministic validators rather than an unconstrained model self-critique.

Recommended retry boundary:

- normal network and rate-limit retries;
- at most one semantic selection repair;
- no open-ended self-reflection loop;
- deterministic fallback or no report after the retry fails.

## Keep post-processing narrowly mechanical

Safe post-processing includes:

- removing duplicate candidate IDs;
- restoring canonical ordering;
- applying maximum claim counts;
- mapping candidate IDs back to repository-owned claims;
- deterministic section grouping;
- deterministic rendering.

Unsafe post-processing includes silently:

- relabelling intent;
- changing evidence operands;
- splitting a model-created claim;
- replacing evidence;
- changing comparison meaning.

Those semantic operations should happen before the model call in candidate compilation, not afterward as repairs.

## Where a second model might help

A second model is unnecessary for groundedness or schema validation. Repository code can do those better.

It may be useful for a subjective editorial question:

> Is this selected set materially useful and non-redundant for the target reader?

Even there, first test a deterministic ranker. A second LLM adds cost, latency and correlated failure modes. It should be introduced only if human evaluation shows the selector regularly chooses valid but uninteresting claims.

## Recommended CryptoPulse redesign

Replace the current claim-plan contract with three smaller artefacts.

### Claim candidate

Entirely repository-owned:

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

### Model selection

The only model-owned output:

```json
{
  "selected_candidate_ids": [
    "claim-017",
    "claim-029",
    "claim-006"
  ]
}
```

### Canonical plan

Reconstructed entirely by the repository from selected IDs:

```json
{
  "claim_plan_version": "...",
  "evidence_bundle_id": "...",
  "analysis_order": ["market_snapshot", "data_quality"],
  "sections": []
}
```

The existing validator can remain as defence in depth, but the candidate compiler should make most semantic errors unreachable.

## Evaluation after redesign

The evaluation becomes clearer:

1. **Candidate recall:** did the deterministic compiler generate every valid useful claim?
2. **Selection precision:** how many chosen candidates were useful?
3. **Selection recall:** did it choose the important candidates?
4. **Redundancy:** did it choose overlapping candidates?
5. **Stability:** does it make similar selections across repeats?
6. **Incremental value:** does it outperform the deterministic ranker?

Schema validity and evidence groundedness should approach 100% by construction and should no longer dominate model evaluation.

## Recommendation

Pause further prompt-version work and the pending Sol/Nex paid calibration.

The next delivery slice should be:

> **Compile valid claim candidates deterministically and reduce the LLM role to bounded candidate selection.**

Build a no-LLM ranking baseline first. Then compare GPT-5.6 Luna and perhaps Nex using the small selection tool on the existing corpus.

This is not giving up on the model. It places the model at the point where it adds genuine value: deciding what is interesting, rather than asking it to reproduce rules the repository already knows.

## References

- [OpenAI structured outputs](https://platform.openai.com/docs/guides/structured-outputs)
- [JSONSchemaBench: A Rigorous Benchmark of Structured Outputs for Language Models](https://arxiv.org/abs/2408.11061)
- [PICARD: Parsing Incrementally for Constrained Auto-Regressive Decoding from Language Models](https://arxiv.org/abs/2109.05093)
- [Data-to-text generation with content planning](https://arxiv.org/abs/1809.00582)
- [OpenAI function calling](https://platform.openai.com/docs/guides/function-calling)
- [Anthropic tool use](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/implement-tool-use)
- [Instructor retrying and validation](https://python.useinstructor.com/concepts/retrying/)
- [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651)
