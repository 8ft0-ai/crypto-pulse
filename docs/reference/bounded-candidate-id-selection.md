# Bounded candidate-ID selection

> **Mode:** Reference  
> **Audience:** CryptoPulse developers, reviewers and governance stakeholders  
> **Outcome:** Look up the optional Phase 6 selector contract, validation rules, one-repair boundary and deterministic fallback behaviour.

## Canonical artefacts

| Artefact | Canonical path |
| --- | --- |
| Selection response schema | [`schemas/crypto-market-candidate-selection-v1.json`](../../schemas/crypto-market-candidate-selection-v1.json) |
| Selection prompt contract | [`prompts/crypto-market-candidate-selection-v1.txt`](../../prompts/crypto-market-candidate-selection-v1.txt) |
| Request, response and diagnostic contract | [`llm_analysis/candidate_selection_contract.py`](../../llm_analysis/candidate_selection_contract.py) |
| Selector orchestration and fallback | [`llm_analysis/candidate_selector.py`](../../llm_analysis/candidate_selector.py) |
| Canonical retained-proof entrypoint | [`llm_analysis/candidate_selection_proof.py`](../../llm_analysis/candidate_selection_proof.py) |
| Offline proof evaluator | [`llm_analysis/candidate_selection_evaluation.py`](../../llm_analysis/candidate_selection_evaluation.py) |
| Evaluation-only invalid fixtures | [`llm_analysis/candidate_selection_validation_proof.py`](../../llm_analysis/candidate_selection_validation_proof.py) |
| Retained proof summary | [`evaluation/phase-06/candidate-selection/summary.json`](../../evaluation/phase-06/candidate-selection/summary.json) |
| Retained scenario records | [`evaluation/phase-06/candidate-selection/scenarios.json`](../../evaluation/phase-06/candidate-selection/scenarios.json) |
| Representative request | [`evaluation/phase-06/candidate-selection/representative-request.json`](../../evaluation/phase-06/candidate-selection/representative-request.json) |
| Representative repair | [`evaluation/phase-06/candidate-selection/representative-repair.json`](../../evaluation/phase-06/candidate-selection/representative-repair.json) |
| Representative plan and render | [`evaluation/phase-06/candidate-selection/representative-plan.json`](../../evaluation/phase-06/candidate-selection/representative-plan.json), [`representative-render.md`](../../evaluation/phase-06/candidate-selection/representative-render.md) |
| Reviewer report | [`evaluation/phase-06/candidate-selection/review.md`](../../evaluation/phase-06/candidate-selection/review.md) |
| Permanent tests | [`tests/test_candidate_selection.py`](../../tests/test_candidate_selection.py) |

This contract implements Phase 6 Slice 5 under issue #293. It does not evaluate a real model. Slice 6 must separately approve any provider, model, case, repeat and cost plan.

## Responsibility boundary

The optional model owns one thing: choosing candidate IDs from the supplied catalogue.

The repository owns:

- candidate compilation, identity and canonical order;
- the candidate catalogue and selector-request identity;
- the response schema and provider-only projection;
- exact-ID, uniqueness, count, section, intent, bundle and redundancy checks;
- stable machine-readable diagnostics;
- the one semantic-repair allowance;
- deterministic fallback;
- claim-plan reconstruction, validation and rendering;
- retained request, response, repair, fallback and output evidence.

The model cannot author or change evidence IDs, intent, comparison relation, section, subject, metric, confidence, values, units, dates, labels, prose or claim features.

## Canonical response

The entire canonical model response is:

```json
{
  "selected_candidate_ids": [
    "claim-candidate:sha256:..."
  ]
}
```

The root object has `additionalProperties: false`. The array must contain one to seven unique IDs matching the content-derived candidate-ID syntax. No rationale, score, priority or ordering metadata is accepted.

The provider-only strict-output projection removes `uniqueItems` because the OpenAI-compatible constrained-decoding subset cannot enforce it. The unchanged canonical repository schema and semantic validator remain authoritative.

## Selector request

`build_candidate_selector_request` first restores the complete candidate set to canonical candidate order. It rejects an empty set, invalid or duplicate candidate identities and candidates belonging to another evidence bundle.

The request records:

- request contract version;
- evidence-bundle ID;
- canonical candidate-set hash;
- ranking version and configuration hash;
- maximum selection count;
- section and intent limits;
- response-schema version;
- the ordered repository-owned candidate catalogue;
- a content-derived request ID.

Each catalogue row contains only structured repository-owned candidate data:

```text
candidate_id
intent
evidence_ids
comparison_relation
section
subject
metric
confidence
bounded candidate features
```

Source text, report prose and instructions embedded in evidence do not enter the catalogue. Equivalent candidate traversal orders produce identical request bytes and request IDs.

## Validation

`validate_candidate_selection` separates malformed envelopes from repairable semantic ID-list failures.

### Malformed envelope

A response is malformed when it is not one object, contains a property other than `selected_candidate_ids`, or does not provide an array. It is not eligible for semantic repair and causes immediate deterministic fallback.

### Repairable semantic selection

A correctly shaped array is checked for:

- at least one ID;
- no more than the configured maximum;
- candidate-ID syntax;
- uniqueness;
- exact membership in the supplied candidate set;
- evidence-bundle identity;
- section limits;
- intent limits;
- one candidate per redundancy group.

The last four checks use the hardened Slice 4 reconstruction boundary. Accepted IDs are then restored to canonical candidate order. The model's array order never controls claim or section order.

### Diagnostics

Diagnostics are bounded objects. Depending on the failure, they contain only fields such as:

```json
{
  "code": "unknown_selected_candidate_id",
  "path": "$.selected_candidate_ids[0]",
  "candidate_id": "claim-candidate:sha256:..."
}
```

Stable codes retained by the proof include:

| Condition | Code |
| --- | --- |
| Unknown ID | `unknown_selected_candidate_id` |
| Duplicate ID | `duplicate_selection` |
| Excessive selection | `excessive_selection` |
| Repeated redundancy group | `selection_redundancy_violation` |
| Candidate from another bundle | `selected_candidate_bundle_mismatch` |

Diagnostics do not contain free-form coaching or replacement claims.

## One-repair state machine

The orchestration state machine is:

```text
initial selector call
  ├─ valid ID array ───────────────→ accept
  ├─ malformed envelope ──────────→ deterministic fallback
  ├─ client/provider-class error ─→ deterministic fallback
  └─ semantic ID-list failure
       ↓
     one machine-readable repair call
       ├─ valid ID array ─────────→ accept after repair
       └─ any failure ────────────→ deterministic fallback
```

There is no third selector call. Transport, authentication, billing, timeout, model-identity and malformed-envelope failures do not consume a semantic repair call because they do not represent a correctable selection decision.

The repair object contains only:

- repair version;
- unchanged request ID;
- previous raw-response hash;
- previous canonical response;
- machine-readable diagnostics;
- unchanged response-schema version.

## Deterministic fallback

The selector computes the Slice 4 deterministic baseline before calling the optional client. Any unrepaired failure returns that complete baseline result.

Fallback never:

- merges partial model IDs with baseline IDs;
- preserves a subset from an invalid response;
- changes ranking configuration;
- creates a new plan from unvalidated IDs;
- requires a provider secret.

The retained proof compares fallback selected IDs, canonical plan bytes and rendered Markdown bytes against the direct Slice 4 baseline. All 15 fallback scenarios match exactly.

## Accepted-selection path

An accepted selection is converted into the repository-owned selection envelope:

```json
{
  "evidence_bundle_id": "sha256:...",
  "selected_candidate_ids": ["claim-candidate:sha256:..."]
}
```

The hardened reconstruction boundary resolves each candidate and copies only its existing intent, evidence IDs, comparison relation, confidence and section into the canonical claim plan. The existing validator then applies schema, referential, value, semantic and policy checks. The existing deterministic renderer produces Markdown only after validation succeeds.

## Retained offline proof

The proof uses scripted provider-agnostic clients over the same five frozen cases as Slices 3 and 4. It makes no network or provider call.

| Measure | Retained result |
| --- | ---: |
| Frozen cases | 5 |
| Scripted scenarios | 25 |
| Scripted selector attempts | 35 |
| First-pass acceptances | 5 |
| Acceptances after one repair | 5 |
| Deterministic fallbacks | 15 |
| Exact fallback matches | 15 / 15 |
| Maximum semantic repairs | 1 |
| Candidate-order permutation stability | 5 / 5 |
| Evidence-order permutation stability | 5 / 5 |
| Real provider calls | 0 |

Every case proves five control-flow scenarios:

1. valid first response;
2. invalid first response followed by valid repair;
3. invalid first response followed by invalid repair;
4. malformed response envelope;
5. client/provider-class failure.

The representative material-movement request contains the complete 230-candidate canonical catalogue. Its accepted response is deliberately supplied in reverse model order; the retained plan restores canonical candidate order and renders a valid five-claim report.

Evaluation-only mutations used to prove redundancy and mixed-bundle rejection are not historical evidence and are not added to compiler output.

## Reproducing the proof

Write the retained files:

```bash
python -m llm_analysis.candidate_selection_proof
```

Check the committed files without rewriting them:

```bash
python -m llm_analysis.candidate_selection_proof --check
```

The permanent unit test regenerates and byte-compares every retained file.

## Security and operational boundaries

Slice 5 adds no concrete provider client, credential lookup, workflow dispatch, automatic report generation or publication route. `ScriptedCandidateSelectorClient` is an offline test double, not a production provider adapter.

A future Slice 6 adapter must still preserve:

- exact model and provider identity controls;
- data-collection and input-classification policy;
- request, token, timeout and cost bounds;
- raw response hashing and provenance;
- the one-repair ceiling;
- deterministic fallback;
- normal pull-request review and publication authority.

The existence of this selector boundary is not a decision to retain a model. Slice 6 must measure incremental editorial value against the permanent deterministic baseline before any repeated use is approved.
