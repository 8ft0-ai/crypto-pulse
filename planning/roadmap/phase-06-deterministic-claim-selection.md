# Phase 6 — Deterministic claim candidates and bounded model selection

Status: shaping.

Parent implementation issue: #283  
Governance transition issue: #282

This is a forward-looking roadmap specification. It records the direction approved after the Phase 5 semantic claim-plan evaluation and does not itself implement candidate compilation, model selection, automatic report generation or publication.

## Context

Phase 5 progressively reduced model responsibility:

```text
model-authored report prose
  -> model-authored semantic claim plan
  -> repository-owned deterministic rendering
```

The semantic claim-plan experiments proved that deterministic rendering and fail-closed validation work, but they also showed that the model was still being asked to reproduce too much repository-owned semantics in one generation.

The model had to:

- interpret heterogeneous evidence;
- choose an allowed claim intent;
- discover claim boundaries;
- select compatible evidence operands;
- derive comparison cardinality and relation;
- distinguish source status from data quality;
- preserve one-source status grouping;
- choose sections and ordering;
- emit the complete nested claim-plan schema;
- satisfy semantic invariants that JSON Schema cannot fully express.

Protected corrective run `29285569716` used prompt `crypto-market-claim-plan/v2`, representative route probes and corrected output envelopes. All three route probes and all three full-contract calls completed, but no model produced a validator-accepted plan:

- GPT-5.6 Luna returned a mostly coherent plan but selected a four-operand comparison and an unsupported data-quality limitation;
- DeepSeek V4 Flash ignored the required top-level claim-plan shape, produced 7,582 output tokens and required about 250 seconds;
- Qwen3.6 Flash completed within its corrected token allowance but returned an invented wrapper and unsupported schema fields.

The reviewed evidence is recorded in [`../../evaluation/phase-05/corrective-screen-29285569716.md`](../../evaluation/phase-05/corrective-screen-29285569716.md). The architectural reasoning is retained in:

- [`../../docs/notes/simplifying-semantic-claim-plan-pipeline.md`](../../docs/notes/simplifying-semantic-claim-plan-pipeline.md);
- [`../../docs/notes/semantic-claim-selection-implementation-patterns.md`](../../docs/notes/semantic-claim-selection-implementation-patterns.md).

## Decision

Repository code will construct all semantically valid claim candidates. A model, if used, may only choose a bounded set of existing candidate IDs.

The model will not author or alter:

- evidence identifiers;
- claim intent;
- evidence operands;
- comparison relation;
- source subject;
- data-quality eligibility;
- section eligibility;
- exact values, units, labels, dates or prose.

This changes the optional model role from **semantic construction** to **editorial selection**.

## Goal

Prove a complete deterministic path from canonical evidence to a useful selected claim set and rendered report, then determine whether a bounded model selector adds measurable editorial value over that deterministic baseline.

The phase should answer two questions in order:

1. Can repository code compile, rank, select, reconstruct and render a useful report without an LLM?
2. Does a model selecting candidate IDs improve usefulness enough to justify its cost, latency and operational complexity?

## Non-goals

Phase 6 does not introduce:

```text
No further tuning of the full semantic claim-plan prompt.
No model-authored evidence IDs, intents, operands, relations or sections.
No model-authored values, dates, labels, explanations or report prose.
No model-side browsing, data collection or source selection.
No automatic report generation or publication.
No production model selection in the initial implementation slices.
No repeated paid evaluation without a separately reviewed issue and cost plan.
No deletion or rewriting of historical Phase 5 prompts, runners, configurations or evidence.
No weakening of data-collection denial, exact-model identity or cross-model fallback controls.
No committed provider completions, secrets or generated `_site/` output.
```

## Responsibility split

| Responsibility | Owner |
| --- | --- |
| Evidence normalisation and canonical fields | Repository |
| Candidate identity and deterministic ordering | Repository |
| Valid absolute and directional claims | Repository |
| Compatible comparison pairs and relation | Repository |
| Source-status boundaries | Repository |
| Data-quality and snapshot-status eligibility | Repository |
| Evidence IDs, intent, section and subject | Repository candidate |
| Candidate features and redundancy groups | Repository |
| Baseline ranking and fallback | Repository |
| Editorial usefulness among valid candidates | Deterministic ranker first; optional model later |
| Canonical plan reconstruction | Repository |
| Exact values, labels, templates and Markdown | Repository renderer |
| Merge and publication authority | Normal repository review process |

## Target pipeline

```text
validated source snapshot
    ↓
canonical evidence bundle and normalisation
    ↓
deterministic claim-candidate compiler
    ↓
candidate validation and feature calculation
    ↓
deterministic ranking baseline
    ↓
selected candidate IDs
    ↓
repository-owned canonical plan reconstruction
    ↓
existing fail-closed validator
    ↓
existing deterministic renderer
    ↓
normal review and publication boundary
```

An optional model-selection path may later replace only the `selected candidate IDs` step:

```text
valid candidate set
    ↓
model selects bounded candidate IDs
    ↓
selection validator
    ↓
at most one machine-readable repair attempt
    ↓
accepted selection or deterministic baseline fallback
```

## Core artefacts

### Repository-owned claim candidate

The initial candidate contract should resemble:

```json
{
  "candidate_version": "crypto-market-claim-candidate/v1",
  "candidate_id": "claim-017",
  "intent": "comparison",
  "evidence_ids": ["evidence-1", "evidence-2"],
  "comparison_relation": "not_equal",
  "section": "market_snapshot",
  "subject": "bitcoin",
  "features": {
    "materiality": "medium",
    "cross_source": true,
    "redundancy_group": "bitcoin_spot_price"
  }
}
```

The exact schema belongs to Slice 1. Candidate IDs must be content-derived or otherwise deterministic and byte-stable for identical inputs.

### Model-owned selection

The optional model contract should contain candidate IDs only:

```json
{
  "selected_candidate_ids": [
    "claim-017",
    "claim-029",
    "claim-006"
  ]
}
```

No free-form rationale is required. The repository can calculate ordering deterministically or permit only a bounded priority field if later evidence proves it useful.

### Repository-reconstructed canonical plan

Repository code resolves selected IDs into the complete canonical plan expected by the existing validator and renderer. The model cannot change the meaning of a candidate during reconstruction.

## Implementation slices

Parent issue #283 is the canonical delivery checklist. Each slice should become a linked child issue when implementation begins.

### Slice 1 — Define the claim-candidate contract

Deliver:

- versioned JSON Schema;
- stable candidate ID and ordering policy;
- allowed candidate intents and feature vocabulary;
- explicit repository/model responsibility boundary;
- valid and invalid fixtures;
- deterministic schema projection only where provider use will later require it.

Exit criteria:

- no candidate field permits model-authored prose or values;
- candidate identity is deterministic;
- the contract can represent every currently supported renderer intent;
- historical claim-plan contracts remain unchanged.

### Slice 2 — Implement deterministic candidate compilation

Compile only repository-valid candidates for:

- absolute observations;
- directional observations;
- compatible two-operand comparisons;
- one-source status claims;
- explicit data-quality limitations;
- supported snapshot-status claims.

Exit criteria:

- incompatible comparisons are never offered;
- source subjects cannot be mixed;
- non-quality metadata cannot become a data-quality limitation;
- invented intents are structurally impossible;
- every emitted candidate can reconstruct to a validator-accepted claim.

### Slice 3 — Build a reviewed gold candidate corpus

Use the frozen Phase 5 cases and deterministic mutations to record expected candidate sets.

Measure:

- candidate recall;
- absence of invalid combinations;
- stable IDs and ordering;
- cross-source normalisation outcomes;
- explicit omissions and rationale.

Exit criteria:

- a reviewer can identify every expected useful candidate without running a model;
- candidate compiler gaps are visible before ranking or selection begins;
- evaluation-only mutations remain clearly separated from historical facts.

### Slice 4 — Implement a deterministic ranking baseline

Rank valid candidates using bounded repository-owned features such as:

```text
material movement
explicit source disagreement
cross-source corroboration
data-quality significance
subject diversity
section coverage
recency
redundancy penalty
```

Exit criteria:

- the baseline produces a bounded non-redundant selection;
- a complete canonical plan is reconstructed and rendered without an LLM;
- identical inputs produce byte-identical selections and reports;
- the baseline is retained as the permanent fallback and evaluation comparator.

### Slice 5 — Add bounded candidate-ID model selection

Only after Slice 4 is complete, add an optional selection tool or strict response contract.

Guardrails:

- every ID must exist in the supplied candidate set;
- IDs must be unique;
- maximum selection count is enforced;
- redundancy-group rules are enforced;
- no new claim semantics may be supplied;
- at most one semantic repair is allowed using machine-readable validator feedback;
- failure falls back to the deterministic baseline or no optional analysis.

Exit criteria:

- invalid model output cannot alter claim meaning;
- groundedness is structural through candidate identity;
- request, response, validation and reconstruction artefacts are retained;
- no automatic generation or publication is enabled.

### Slice 6 — Compare model selection with the deterministic baseline

Evaluate one or two separately approved candidates only after the preceding slices are complete.

Measure:

- useful-candidate precision;
- important-candidate recall;
- redundancy;
- stability across repeats;
- latency;
- cost;
- incremental value over the deterministic ranker.

Do not treat schema validity or evidence groundedness as model-quality differentiators; those should be guaranteed by construction.

Exit criteria:

- the baseline and model receive the same candidate set;
- human review criteria are defined before paid calls;
- any repeated evaluation has a checked-in case, repeat and cost plan;
- a separate reviewed decision records whether model selection adds enough value to retain.

## Acceptance gates

Phase 6 may progress to optional model evaluation only when:

- [ ] the candidate schema is versioned and source-controlled;
- [ ] the compiler is deterministic and emits only validator-compatible candidates;
- [ ] the reviewed gold corpus records candidate recall and deliberate omissions;
- [ ] stable candidate identity and ordering are proven;
- [ ] the deterministic baseline reconstructs and renders complete reports;
- [ ] the baseline remains available with no provider secret;
- [ ] model output is limited to candidate IDs;
- [ ] invalid IDs, duplicates, excessive selection and redundancy violations fail closed;
- [ ] at most one semantic repair is enforced;
- [ ] deterministic fallback is proven;
- [ ] automatic generation and publication remain disabled;
- [ ] full repository CI passes;
- [ ] generated `_site/` output is not committed.

## Evaluation model

The primary Phase 6 measures are:

1. **Candidate recall** — did the compiler generate every useful valid candidate?
2. **Selection precision** — how many selected candidates were useful?
3. **Selection recall** — were important candidates selected?
4. **Redundancy** — were overlapping candidates selected together?
5. **Stability** — are selections consistent across repeats?
6. **Incremental value** — does the model outperform the deterministic baseline?

Schema validity, evidence references and semantic compatibility should approach 100% by construction and remain defence-in-depth validation rather than the main model benchmark.

## Risks and mitigations

### Candidate explosion

Compatible pair enumeration may create too many candidates.

Mitigation: apply deterministic compatibility, materiality and redundancy filters before any selector sees the set; retain counts and reasons for filtered candidates.

### Compiler omits a useful claim

A selector cannot choose a candidate that was never generated.

Mitigation: prioritise the reviewed gold corpus and candidate-recall testing before ranking or model work.

### Deterministic baseline is valid but dull

A rule-based selection may over-prioritise routine facts.

Mitigation: make editorial features explicit and reviewable; compare any optional model against the baseline rather than assuming a model is required.

### Model selection adds little value

A model may choose the same candidates as the baseline while adding cost and operational risk.

Mitigation: require measurable incremental value before retaining model selection.

### Repair loops become open-ended

Repeated retries can hide contract defects and increase cost.

Mitigation: allow normal transport retries and at most one semantic selection repair; otherwise use the deterministic baseline or fail closed.

### Historical evidence becomes confused with the new contract

Phase 5 contains several immutable prompts, runners and evaluations.

Mitigation: preserve all historical artefacts and remove only obsolete manual workflow entry points. Mark historical documentation explicitly and link the Phase 6 decision record.

## Historical treatment and migration

Phase 5 remains valuable evidence:

- the evidence bundle, semantic validator and deterministic renderer are retained;
- claim-plan v1 and v2 prompts and schemas remain immutable historical contracts;
- calibration runners and source-controlled plans remain auditable;
- protected run artefacts and reviewed decisions remain linked;
- obsolete full-plan workflow files are removed from the Actions UI to prevent accidental dispatch.

Phase 6 may reuse validator and renderer components, but it must introduce new candidate and selection contracts rather than mutating the historical claim-plan contracts in place.

## Definition of done

Phase 6 is complete when:

- [ ] parent issue #283 and linked slice issues are complete;
- [ ] all six slices have merged implementation and validation evidence;
- [ ] the deterministic baseline produces complete reports over the reviewed corpus;
- [ ] model selection, if retained, is structurally unable to author claim semantics;
- [ ] comparative evidence records whether model selection adds value;
- [ ] a reviewed decision is committed;
- [ ] a Phase 6 delivery record is added under `planning/delivery/`;
- [ ] `planning/delivery-log.md` is updated;
- [ ] `planning/delivery/delivery.yaml` and graph are updated or explicitly marked not applicable;
- [ ] automatic generation and publication remain separately governed;
- [ ] generated `_site/` output is not committed.
