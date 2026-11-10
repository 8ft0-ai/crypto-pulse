# Phase 6 — Bounded candidate-selector comparison decision

Status: approved.  
Decision date: 2026-08-03.  
Decision issue: #310  
Parent phase: #283  
Comparison issue: #295  
Corrective transport issue: #300

## Decision

The deterministic Slice 4 selector remains the **only supported active candidate-selection path**.

Bounded model selection is removed from the active CryptoPulse roadmap. The Slice 5 candidate-ID-only contracts, validators, deterministic fallback, runners, configurations, documentation and retained protected evidence remain available as inactive research and audit artefacts, but no model selector is enabled for production, scheduling, automatic report generation or publication.

No further paid Phase 6 comparison run is authorised. Any future investigation of model-based candidate selection requires a new phase, a new reviewed evidence plan, a new cost envelope and explicit repository-owner authority.

## Evaluation classification

The protected model comparison is classified as:

```text
inconclusive-infrastructure
```

This is distinct from the roadmap decision above.

Neither protected attempt completed the fixed comparison corpus, so the predeclared Gate A quality upper-bound rule cannot be formally adjudicated. The roadmap decision must not be represented as a formal model-quality failure. It is instead a governance decision based on insufficient complete evidence after two bounded attempts, repeated failure of fixed cost-governance limits, weak diagnostic results from the completed final-run repeats and operational complexity that did not demonstrate incremental editorial value.

## Retained deterministic baseline

The repository-owned comparator remains fully usable without a provider secret:

```text
Selected candidates:        35
Reviewed-useful selected:   26
Reviewed-useful expected:   38
Precision:                  74.285714%
Recall:                     68.421053%
F1:                         71.232877%
Validated plans:            5 / 5
Rendered reports:           5 / 5
Provider calls:             0
```

The retained architecture is:

```text
canonical evidence
  -> deterministic claim-candidate compilation
  -> deterministic candidate ranking and selection
  -> repository-owned canonical plan reconstruction
  -> fail-closed semantic validation
  -> deterministic rendering
```

This path remains byte-stable for identical inputs and remains the fallback boundary for the inactive Slice 5 selector contract.

## Protected attempt 1

Run: `30771922641`  
Trusted SHA: `dff2f609343be96c76ad646b8e2eaa97ad8e3b3e`

Secret-free preparation regenerated the deterministic baseline successfully. The exact route probe also succeeded:

```text
Requested model:  openai/gpt-5.6-sol
Actual model:     openai/gpt-5.6-sol
Actual provider:  OpenAI
Route cost:       USD 0.000715
```

The first corpus call then used 35,806 input tokens, exhausted its 512-token output allowance and cost USD `0.23914375` against the reviewed USD `0.12` per-call ceiling. The metered response was retained before the run failed closed. No second corpus call and no Nex N2 Mini call occurred.

Protected artefact:

```text
Artifact ID: 8840792374
Digest: sha256:a0c4d542d6fdfac5cc03a1167aca62da9ab675f40dd7b91618932571f70a3629
```

The result was correctly recorded as infrastructure-inconclusive. It provided no accepted model-quality result.

## Corrective transport

Issue #300 and PR #301 preserved the complete canonical candidate set while adding a compact provider-only catalogue projection, increasing the GPT output cap to 1,024 tokens, recalibrating bounded execution ceilings and adding decisive stopping after two fully metered model fallbacks.

The correction did not add a candidate shortlist, remove candidates, alter reviewed useful expectations, permit model-authored semantics, substitute providers, add a third model or enable production use.

## Protected attempt 2 — final run

Run: `30777564268`  
Trusted SHA: `40c9fd533dd79bb4b4a6c8bd1f232646bf1f37c5`

The fresh one-time guard, secret-free preparation and exact route probe succeeded. The route again resolved to the requested GPT/OpenAI identity at USD `0.000715`.

Three complete GPT repeats were retained for `historical-degraded-sparse`:

| Repeat | Outcome | Precision | Recall | F1 | Cost | Latency |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | Accepted initial selection | 28.57% | 25.00% | 26.67% | USD 0.1424575 | 12.714 s |
| 2 | Deterministic fallback after malformed length-limited envelope | 0% | 0% | 0% | USD 0.040352 | 49.367 s |
| 3 | Accepted initial selection | 42.86% | 37.50% | 40.00% | USD 0.033482 | 24.674 s |

These rows are diagnostic only. They cover one of five cases, include one fallback in three runs and are materially below the predeclared aggregate quality thresholds. They cannot be extrapolated into a formal Gate A result.

The next call, `historical-normal-crosschecked` repeat 1, used the exact requested model and provider and returned a complete seven-ID envelope, but exceeded the fixed per-call ceiling:

```text
Request bytes:    59,849
Input tokens:     21,440
Output tokens:    814
Reasoning tokens: 484
Finish reason:    stop
Reported cost:    USD 0.15841625
Configured cap:   USD 0.15
```

The response and metering evidence were persisted before abort. It receives no model-quality credit because it exceeded the reviewed limit. No later GPT call and no Nex N2 Mini call occurred.

Total reported spend for the final run, including the route probe and four corpus calls, was USD `0.37542275`.

Retained artefacts:

```text
Prepared artifact ID: 8842553997
Prepared digest: sha256:6b39ca56a84bbdc3dcd63e438fce0b5401e75da95dbeae3c5a3a46f108c72204

Protected artifact ID: 8842583436
Protected digest: sha256:a40c94efcc7c125026abfc69d942eeb7ae70e210f81c366b4319dcecab7e54c7
```

## Nex N2 Mini conclusion

No Nex N2 Mini corpus call occurred in either protected attempt. This record makes **no Nex quality, latency, stability or deployment conclusion**.

Nex is not retained as an active deployment candidate because the governed comparison never reached it and the final-run stop-loss prohibits another Phase 6 attempt. This is an evidence and governance boundary, not a claim that Nex failed the predeclared deployment gate.

## Rationale

The deterministic selector is already complete, valid, auditable and free of provider cost. Retaining an active model-selector direction therefore requires positive evidence of incremental editorial value, not merely evidence that provider transport can eventually be made to run.

After two protected attempts:

- neither fixed corpus completed;
- both attempts exceeded reviewed per-call cost ceilings;
- the final attempt produced only three scored repeats from one case;
- one of those three repeats used deterministic fallback;
- the two accepted diagnostic selections had F1 scores of 26.67% and 40.00%;
- no Nex evidence exists;
- additional calibration would require another paid run and another change to reviewed limits.

That evidence is insufficient to justify the continuing cost, latency and operational surface of active bounded model selection. The correct default is therefore the proven deterministic path.

## Operational consequences

- The deterministic selector remains the only active selector and comparator.
- Candidate compilation, evidence ownership, semantic meaning, plan reconstruction, validation and rendering remain repository-owned.
- Slice 5 model-selection code remains inactive and may be used only as historical or research material.
- The protected Slice 6 comparison workflow must not be dispatched again under Phase 6 and its manual entry point should be archived during phase close-out.
- No provider, model alias, third model, free-model sweep, prompt retuning or cost-ceiling increase is authorised.
- Automatic generation and publication remain disabled and separately governed.
- Raw provider output remains protected workflow evidence rather than committed repository content.
- Historical Phase 5 and Phase 6 prompts, configurations, runners, decisions and Git history remain auditable.

## Future reconsideration

A future phase may reconsider bounded model selection only when it begins with materially new evidence or architecture rather than another calibration of this run. At minimum it must define:

- the decision the model is expected to improve;
- a deterministic comparator;
- a fixed reviewed corpus and human criteria;
- a realistic, independently calibrated transport and cost plan;
- explicit model/provider identities and fallback policy;
- a stop-loss;
- separate authority for paid execution and any operational enablement.

Until such a phase is approved, deterministic selection is final for the current roadmap.
