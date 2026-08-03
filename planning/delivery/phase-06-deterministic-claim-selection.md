# Phase 6 — Deterministic claim candidates and bounded model selection

Status: complete.

## Outcome

Phase 6 moved claim semantics out of the model boundary and into deterministic repository code. CryptoPulse can now compile valid claim candidates, select a bounded non-redundant set, reconstruct a canonical claim plan, validate it and render complete reports without an LLM.

A separately governed candidate-ID-only model path was implemented and evaluated, but it did not produce sufficient complete evidence to justify an active model selector. Both protected comparisons failed closed on fixed per-call cost ceilings. The final reviewed decision retains deterministic selection as the sole active selector and archives bounded model selection as inactive research and audit material.

## Delivery scope

Parent issue: #283  
Governance transition: #282 / PR #284  
Implementation slices: #285, #287, #289, #291, #293, #295  
Corrective transport: #300 / PR #301  
Final decision: #310 / PR #311  
Delivery close-out: #312

### Slice 1 — candidate contract

```text
Issue: #285
PR: #286
Merge commit: b13ea0b796c5a1cc69ed7600ea963f775a6728a2
Validation run: 30739481644
```

Delivered a versioned `crypto-market-claim-candidate/v1` schema, content-derived candidate IDs, canonical semantic normalisation, deterministic ordering and fail-closed exact-ID indexing. Candidate identity excludes ranking features and prohibits model-authored prose, values and explanations.

### Slice 2 — deterministic compilation

```text
Issue: #287
PR: #288
Merge commit: 4df11666d6c35c13263f08b6dd3c74ef6068098f
Validation run: 30741305435
```

Delivered repository-owned compilation for absolute observations, directional observations, compatible two-operand comparisons, one-source status, supported data-quality limitations and snapshot status. Every emitted candidate is validator- and renderer-compatible by construction.

### Slice 3 — reviewed gold corpus

```text
Issue: #289
PR: #290
Merge commit: 17cac7f36eb7d45178dad5db2f7c1f3b17462388
Validation run: 30743936885
```

Delivered a reviewed five-case corpus with 38 useful expectations, 100% candidate recall, 20 prohibited-combination checks with zero matches, stable complete-candidate identities and an explicitly evaluation-only cross-source normalisation probe.

### Slice 4 — deterministic ranking and reconstruction

```text
Issue: #291
PR: #292
Merge commit: 668eb91709c5dcbfe94bee2f3b911404cc0c0814
Validation run: 30747425284
```

Delivered the permanent no-LLM baseline: versioned lexicographic ranking, bounded non-redundant selection, canonical plan reconstruction, fail-closed validation and deterministic rendering.

Retained baseline over the five frozen cases:

```text
Candidates per case:          201–230
Selected per case:                  7
Selected candidates:               35
Reviewed-useful selected:          26
Reviewed-useful expected:          38
Precision:                     74.29%
Recall:                        68.42%
F1:                            71.23%
Validated plans:                 5/5
Rendered reports:                5/5
Provider calls:                    0
```

### Slice 5 — candidate-ID-only model boundary

```text
Issue: #293
PR: #294
Merge commit: 754ccf12c96584f45c440d5255738a50720f96c4
Validation run: 30769846015
```

Delivered a strict one-field model response containing existing candidate IDs only. Repository code owns complete request identity, exact membership and uniqueness checks, count, section, intent, bundle and redundancy limits, at most one semantic repair, deterministic fallback, canonical reconstruction, validation and rendering.

Offline retained proof covered 25 scenarios and 35 scripted attempts. All 15 fallback scenarios produced byte-identical baseline IDs, plans and Markdown. No provider call occurred.

### Slice 6 — governed comparison

```text
Issue: #295
Implementation PR: #296
Implementation merge: 44d0265945629c17c360dde9744a4eb7bc969e98
Implementation CI: 30771584033
Corrective issue: #300
Corrective PR: #301
Corrective merge: 3dc41e24cee6d21c0a77cc523927223ad83c0a58
Decision issue: #310
Decision PR: #311
Decision merge: 06320a5598f630a04c3d88353fe7d18361d2fa89
```

The fixed comparison used `openai/gpt-5.6-sol` as a non-deployable quality upper bound and `nex-agi/nex-n2-mini` as the sole deployment candidate. Models could select candidate IDs only; they could not author or alter claim semantics.

## Protected comparison evidence

### Attempt 1

```text
Run: 30771922641
Trusted SHA: dff2f609343be96c76ad646b8e2eaa97ad8e3b3e
Classification: inconclusive-infrastructure
```

The exact GPT/OpenAI route passed. The first full-catalogue corpus call used 35,806 input tokens, exhausted its output allowance and cost USD `0.23914375` against the fixed USD `0.12` per-call limit. The response was retained before the run failed closed. No second corpus call and no Nex call occurred.

```text
Protected artifact: 8840792374
Digest: sha256:a0c4d542d6fdfac5cc03a1167aca62da9ab675f40dd7b91618932571f70a3629
```

### Corrective transport

PR #301 retained the complete canonical candidate set while adding a compact provider-only projection, model-specific output caps, recalibrated cost ceilings and decisive stopping after two fully metered model fallbacks. It did not introduce a shortlist, remove candidates, change reviewed expectations, permit provider substitution or enable production use.

### Attempt 2 — final run

```text
Run: 30777564268
Trusted SHA: 40c9fd533dd79bb4b4a6c8bd1f232646bf1f37c5
Classification: inconclusive-infrastructure
```

The exact route, secret-free preparation and trusted-SHA controls passed. Three complete GPT repeats were retained for one case:

| Repeat | Outcome | Precision | Recall | F1 | Cost |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | Accepted initial | 28.57% | 25.00% | 26.67% | USD 0.1424575 |
| 2 | Deterministic fallback | 0% | 0% | 0% | USD 0.040352 |
| 3 | Accepted initial | 42.86% | 37.50% | 40.00% | USD 0.033482 |

The next exact-route call returned a complete seven-ID envelope but cost USD `0.15841625` against the fixed USD `0.15` per-call ceiling. The metered response was retained before abort. No later GPT call and no Nex call occurred. Total reported final-run spend was USD `0.37542275`.

```text
Prepared artifact: 8842553997
Prepared digest: sha256:6b39ca56a84bbdc3dcd63e438fce0b5401e75da95dbeae3c5a3a46f108c72204
Protected artifact: 8842583436
Protected digest: sha256:a40c94efcc7c125026abfc69d942eeb7ae70e210f81c366b4319dcecab7e54c7
```

The three scored rows are diagnostic only. They cover one case, include one fallback and do not constitute a formal Gate A result. No Nex quality, stability, latency or deployment conclusion is claimed.

## Final decision

The reviewed decision is recorded in:

```text
planning/roadmap/phase-06-bounded-selector-comparison-decision.md
```

The comparison remains formally `inconclusive-infrastructure` because neither corpus completed. Separately, bounded model selection is removed from the active roadmap because two governed attempts produced insufficient complete evidence, repeatedly exceeded fixed per-call limits and did not demonstrate incremental value over the already-proven deterministic path.

The final operating position is:

- deterministic selection is the sole active selector;
- candidate semantics, evidence, ranking, reconstruction, validation and rendering remain repository-owned;
- Slice 5 and Slice 6 model-selection implementation remains inactive historical and research material;
- no further paid Phase 6 run is authorised;
- no provider or model is enabled for production selection;
- automatic report generation and publication remain disabled and separately governed.

## Workflow archival

The manual paid comparison entry point is removed during this close-out so it cannot be dispatched accidentally. The configuration, compact prompt, schemas, runners, scoring code, documentation, tests of retained implementation boundaries, Git history and protected artifact references remain auditable.

## Validation evidence

Every implementation PR passed the repository’s semantic integration, public-data compatibility, full unit, documentation, generated-output and static-site gates before merge.

The final decision PR passed:

```text
Run: 30778001813
Unit tests: 411 passed
Documentation: 159 tracked Markdown files passed
Committed _site rejection: passed
Static-site build: 44 reports
Provider calls: 0
```

The delivery close-out PR reruns the complete gate after workflow archival and planning updates.

## Boundaries preserved

- Model output cannot author evidence IDs, intents, operands, relations, values, dates, labels, sections or prose.
- Candidate and plan meaning remain repository-owned.
- Deterministic fallback never credits model quality.
- Exact requested model and provider identity were enforced during protected runs.
- Every metered provider response was retained before validation or cost failure.
- Sensitive, customer, credential and internal data remained prohibited.
- No report was automatically generated or published by Phase 6.
- `_site/` remains disposable generated output and is not committed.
- Historical Phase 5 and Phase 6 evidence remains intact.

## Delivery graph decision

Delivery graph update: N/A.

Phase 6 replaces an internal semantic-analysis and editorial-selection boundary. It does not add a new production pipeline stage, committed report artefact, deployed service, source-ingestion dependency or publication path. Modelling all six implementation slices and two failed protected evaluations would turn the compact causal graph into an implementation inventory. The phase is therefore represented in this delivery record and `planning/delivery-log.md`, following the established compact-graph precedent used for Phase 4.

## Carry-forward lessons

1. Prove the deterministic comparator before paying for model selection.
2. Keep semantic construction in repository code and make model authority structurally narrow.
3. Calibrate transport and cost with realistic request sizes before authorising a repeated corpus.
4. Treat fixed cost ceilings as governance controls, not values to raise automatically after a miss.
5. Retain incomplete model output as diagnostic evidence without converting it into a formal quality result.
6. Use an explicit stop-loss so infrastructure calibration cannot become an indefinite research loop.
7. Remove obsolete paid workflow entry points after the decision while retaining the evidence and implementation history.
