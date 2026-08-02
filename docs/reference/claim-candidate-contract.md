# Deterministic claim-candidate contract

> **Mode:** Reference  
> **Audience:** CryptoPulse developers, reviewers and governance stakeholders  
> **Outcome:** Look up the versioned repository-owned candidate shape, stable identity algorithm, deterministic ordering and boundary for later selection.

## Canonical artefacts

| Contract | Version | Canonical file |
| --- | --- | --- |
| Claim candidate | `crypto-market-claim-candidate/v1` | [`schemas/crypto-market-claim-candidate-v1.json`](../../schemas/crypto-market-claim-candidate-v1.json) |
| Candidate identity | `crypto-market-claim-candidate-identity/v1` | [`llm_analysis/claim_candidate_contract.py`](../../llm_analysis/claim_candidate_contract.py) |
| Existing claim plan | `crypto-market-claim-plan/v1` | [`schemas/crypto-market-claim-plan-v1.json`](../../schemas/crypto-market-claim-plan-v1.json) |
| Evidence bundle | `crypto-market-evidence-bundle/v1` | [`schemas/crypto-market-evidence-bundle-v1.json`](../../schemas/crypto-market-evidence-bundle-v1.json) |

The candidate contract is the Phase 6 repository boundary. It does not replace or modify the historical Phase 5 claim-plan schema, prompts, validators, runners or evaluation records.

## Responsibility boundary

```text
canonical evidence bundle
        ↓
repository-owned candidate compiler (Slice 2)
        ↓
validated deterministic candidates
        ↓
deterministic baseline or bounded ID selector
        ↓
repository-owned claim-plan reconstruction
        ↓
existing validator and deterministic renderer
```

Repository code owns candidate construction, candidate IDs, intent, evidence references, comparison operands and relation, source grouping, data-quality eligibility, section eligibility, subject and metric identifiers, confidence, semantic validation, plan reconstruction, rendering and publication authority.

A future model may select existing candidate IDs only. It cannot create or alter candidate records, evidence IDs, semantics, values, dates, labels, sections, claim prose or feature values. No model rationale is part of the contract.

## Candidate shape

```text
candidate_version
evidence_bundle_id
candidate_id
intent
evidence_ids[]
comparison_relation
section
subject
  type
  id
metric
confidence
features
  bounded deterministic ranking and editorial metadata
```

The intent, comparison relation, section and confidence vocabularies are reused unchanged from `crypto-market-claim-plan/v1`. `subject` uses the existing evidence-subject type vocabulary but deliberately excludes display names and symbols. `metric` is a stable repository identifier, not a display label.

The schema is closed. It has no field for prose, Markdown, rationale, copied values, units, currencies, dates, timestamps, labels, aliases, causes, advice, recommendations, forecasts, targets, signals, positions or actions.

## Stable candidate identity

Candidate identifiers use:

```text
claim-candidate:sha256:<64 lowercase hexadecimal characters>
```

The digest is SHA-256 over the repository's existing canonical JSON encoding: UTF-8, sorted object keys, compact separators, Unicode preserved and NaN or Infinity rejected.

The hash is domain-separated by `crypto-market-claim-candidate-identity/v1` and includes:

- `candidate_version`;
- `evidence_bundle_id`;
- `intent`;
- canonical `evidence_ids`;
- canonical `comparison_relation`;
- `section`;
- `subject.type` and `subject.id`;
- `metric`;
- `confidence`.

`candidate_id` itself and ranking features are excluded from the identity payload. A ranking-feature change can therefore change editorial treatment without silently changing the semantic identity of the claim. Any change to the evidence bundle, intent, operands, relation, section, subject, metric or confidence changes the ID.

Including `evidence_bundle_id` binds the candidate to the exact canonical evidence content whose values and statuses give the evidence identifiers their meaning. Candidate IDs never depend on list position, traversal order, wall-clock generation time or model output.

### Evidence and comparison canonicalisation

All evidence identifiers are ordered lexically before hashing.

For a comparison, comparison operands are ordered lexically by evidence ID. If repository traversal supplies the pair in reverse order, asymmetric relations are inverted:

```text
greater_than ↔ less_than
```

Symmetric relations remain unchanged:

```text
approximately_equal
not_equal
opposite_direction
```

The relation always describes the first canonical operand relative to the second. Equivalent candidates produced from differently ordered source dictionaries or evidence arrays therefore receive the same ID.

### Collision and duplicate behaviour

The contract fails closed:

- a stored ID that does not match the canonical semantic payload is rejected;
- duplicate IDs in one candidate set are rejected, including byte-identical duplicates;
- an ID collision between different records is rejected and must not be silently replaced;
- a later selected ID must resolve exactly once in the validated candidate index;
- an unknown selected ID must fail closed.

`index_candidates_by_id()` implements the exact-ID and duplicate boundary for already-constructed candidates. It does not perform compilation or selection.

## Deterministic ordering

Two kinds of ordering are separate.

### Semantic canonicalisation

Evidence-ID ordering and comparison operand normalisation are part of semantic identity. Changing the unnormalised traversal order cannot change the candidate ID.

### Presentation ordering

Candidate-list ordering is deterministic but does not affect identity. `candidate_sort_key()` and `order_candidates()` use:

1. claim-plan section precedence;
2. claim intent precedence;
3. subject type;
4. subject ID;
5. metric;
6. canonical evidence-ID tuple;
7. comparison-relation precedence;
8. derived candidate ID as the final tie-breaker.

This gives stable ordering for ordinary observations, comparison pairs, source-status candidates and data-quality candidates even when input dictionaries, evidence arrays or compiler traversal differ. Later ranking may select a subset, but it must not rewrite this candidate meaning.

## Deterministic feature boundary

`features` is repository-calculated metadata for later filtering, ranking, diversity and redundancy handling. The initial bounded vocabulary is:

```text
materiality_bucket
cross_source
conflict_status
recency_bucket
quality_significance
section_eligibility
redundancy_group
corroboration_count
```

Features must be deterministic, reproducible and derived from canonical evidence or reviewed repository configuration. They cannot contain model scores, prose, values copied from evidence, economic advice or unsupported judgements. They are not claim-plan fields and ranking features are excluded from candidate identity.

A feature change must not alter the exact semantic claim. When a proposed feature would change intent, operands, relation, section, subject, metric, confidence or evidence-bundle meaning, it is not a ranking feature; it requires a new candidate and therefore a new ID.

This slice defines feature representation only. It does not implement the Phase 6 ranking algorithm.

## Compatibility with the existing claim plan

`crypto-market-claim-plan/v1` remains unchanged.

One selected candidate maps to one existing claim-plan claim:

| Candidate field | Claim-plan destination |
| --- | --- |
| `candidate_id` | deterministic claim ID derived from, or safely encoded from, the candidate ID by the later reconstruction contract |
| `intent` | `claim.intent` |
| `evidence_ids` | `claim.evidence_ids` |
| `comparison_relation` | `claim.comparison_relation` |
| `confidence` | `claim.confidence` |
| `section` | enclosing `section.section_kind` and `analysis_order` |

`candidate_version`, `evidence_bundle_id`, `subject`, `metric` and `features` remain reconstruction provenance and selection metadata; they are not copied into the claim-plan claim. The reconstructed plan uses the selected candidate set's one exact `evidence_bundle_id` as `claim_plan.evidence_bundle_id`.

The later reconstruction slice must group candidates by canonical section order, reject mixed bundle IDs, reject unknown or duplicate selected IDs, create deterministic bounded claim IDs and pass the unchanged schema and existing semantic validator before rendering.

The candidate version and claim-plan version are independent. A future candidate version may still reconstruct to claim-plan v1 when an explicit reviewed compatibility mapping exists.

## Schema versus later semantic validation

The JSON Schema enforces:

- a closed bounded object shape;
- version and ID formats;
- existing intent, relation, section and confidence enums;
- canonical subject and metric identifier shapes;
- unique evidence references;
- exactly two operands and a non-`none` relation for comparisons;
- `none` for non-comparisons;
- source-subject and section shape for `source_status`;
- snapshot subject shape for `snapshot_status`;
- data-quality section eligibility;
- a closed bounded feature vocabulary.

The Slice 2 compiler and semantic validation must enforce facts that JSON Schema cannot prove:

- every evidence ID exists in the referenced bundle;
- subject and metric match the cited evidence;
- comparison operands are compatible and the relation is true;
- source-status candidates describe exactly one source subject;
- data-quality candidates have explicit missing, failed, stale, degraded, skipped, warning, incomplete or conflicting support;
- healthy coverage metadata is not promoted to a limitation;
- section eligibility and feature derivation follow reviewed repository rules;
- every emitted candidate can reconstruct to a validator-accepted claim.

## Scope boundary

`llm_analysis.claim_candidate_contract` does not compile candidates, calculate evidence-derived features, rank or select candidates, reconstruct a claim plan, call a provider or render prose. Fixtures are contract examples only and authorise no provider call, automatic generation or publication.

Historical Phase 5 prompts v1 and v2, claim-plan schema, validators, renderer, configurations, runners and evaluation evidence remain unchanged and auditable.

Slice 2 remains blocked until issue #285 is complete and the Slice 1 pull request is merged.
