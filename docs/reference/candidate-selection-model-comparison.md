# Governed bounded-selector model comparison

> **Mode:** Historical reference  
> **Audience:** CryptoPulse developers, reviewers and governance stakeholders  
> **Outcome:** Understand the completed Phase 6 Slice 6 comparison contract, retained evidence and final archival boundary.

## Status

The bounded-selector comparison is complete and archived.

The reviewed decision is recorded in:

```text
planning/roadmap/phase-06-bounded-selector-comparison-decision.md
```

The comparison is formally classified as `inconclusive-infrastructure` because neither
protected attempt completed the fixed model corpus. Separately, bounded model selection
was removed from the active roadmap and the deterministic Slice 4 selector remains the
only supported active selector.

The manual paid workflow entry point has been removed. The retained implementation is
historical and must not be used to start another Phase 6 provider run.

## Canonical retained artefacts

| Artefact | Canonical path |
| --- | --- |
| Comparison configuration | [`config/candidate-selection-model-comparison.yml`](../../config/candidate-selection-model-comparison.yml) |
| Compact transport prompt | [`prompts/crypto-market-candidate-selection-compact-v1.txt`](../../prompts/crypto-market-candidate-selection-compact-v1.txt) |
| Compact request projection | [`llm_analysis/candidate_selector_compact_projection.py`](../../llm_analysis/candidate_selector_compact_projection.py) |
| Compact client wrapper | [`llm_analysis/compact_candidate_selector_client.py`](../../llm_analysis/compact_candidate_selector_client.py) |
| Configuration loader | [`llm_analysis/candidate_selection_model_comparison_config.py`](../../llm_analysis/candidate_selection_model_comparison_config.py) |
| OpenRouter selector adapter | [`llm_analysis/openrouter_candidate_selector.py`](../../llm_analysis/openrouter_candidate_selector.py) |
| Comparison evaluator | [`llm_analysis/candidate_selection_model_comparison.py`](../../llm_analysis/candidate_selection_model_comparison.py) |
| Fail-closed protected runner | [`llm_analysis/candidate_selection_model_comparison_runner.py`](../../llm_analysis/candidate_selection_model_comparison_runner.py) |
| Scoring and decision rules | [`llm_analysis/candidate_selection_model_scoring.py`](../../llm_analysis/candidate_selection_model_scoring.py) |
| Evaluation record | [`evaluation/phase-06/candidate-selection-model-comparison/`](../../evaluation/phase-06/candidate-selection-model-comparison/) |
| Final decision | [`planning/roadmap/phase-06-bounded-selector-comparison-decision.md`](../../planning/roadmap/phase-06-bounded-selector-comparison-decision.md) |
| Phase delivery record | [`planning/delivery/phase-06-deterministic-claim-selection.md`](../../planning/delivery/phase-06-deterministic-claim-selection.md) |

The deleted workflow remains available through Git history and the protected run records.
Its absence from `.github/workflows/` is an intentional safety boundary.

## Fixed comparison contract

| Role | Model | Allowed actual provider | Repeats | Output cap |
| --- | --- | --- | ---: | ---: |
| Quality upper bound | `openai/gpt-5.6-sol` | `OpenAI` | 3 per case | 1,024 tokens |
| Deployment candidate | `nex-agi/nex-n2-mini` | `Nex AGI` | 3 per case | 512 tokens |

Each model was intended to receive the same five frozen Slice 3 candidate sets. Model
aliases, router aliases, provider substitution and cross-model fallback were prohibited.
The live catalogue and exact route were checked before corpus calls.

No Nex corpus call occurred in either protected attempt. The retained record therefore
makes no Nex quality, stability, latency or deployment claim.

## Responsibility boundary

The model could choose existing candidate IDs only. Repository code remained authoritative
for:

- exact membership and uniqueness;
- maximum count;
- section and intent limits;
- evidence-bundle identity;
- redundancy groups;
- at most one semantic repair;
- deterministic fallback;
- canonical plan reconstruction;
- semantic validation;
- deterministic rendering.

The model could not author or alter evidence IDs, claim intent, operands, comparison
relation, source subject, data-quality eligibility, section, values, labels, dates or
report prose.

## Compact provider request

Repository records retained the complete canonical selector request. Provider transport
projected each candidate into one positional row containing:

```text
candidate_id, section, intent, subject type, subject id, metric, confidence,
comparison relation, materiality, conflict status, quality significance,
cross-source flag, corroboration count, recency and redundancy group
```

The compact request preserved every full candidate ID and canonical ordering. It omitted
evidence IDs, source prose and repeated verbose property names. Secret-free preparation
verified that each projected request remained below 65,536 bytes.

| Case | Canonical bytes | Compact bytes | Candidates |
| --- | ---: | ---: | ---: |
| Historical degraded/sparse | 125,714 | 45,174 | 201 |
| Historical normal/cross-checked | 142,248 | 50,891 | 229 |
| Historical material move | 142,678 | 51,320 | 230 |
| Adversarial prompt injection | 138,531 | 49,898 | 225 |
| Adversarial source disagreement | 137,419 | 49,693 | 224 |

## Permanent deterministic comparator

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

A first-pass or repaired accepted ID list received model credit. Deterministic fallback
remained the safe output but contributed zero model selection, precision and recall.
Failed repeats remained in stability and aggregate metrics.

## Metering and fail-closed controls

Every metered response was persisted and charged before content, model or provider
validation. Missing trustworthy usage or cost retained a sanitised failure record,
reserved the reviewed ceiling and aborted as infrastructure-inconclusive.

Provider fallback, model/provider substitution and over-cap cost were retained before
abort. Correctly routed malformed JSON remained a metered model failure and entered the
deterministic fallback boundary. Network retry was disabled.

The final checked-in limits were:

```text
Logical selector runs:                    30 maximum
Substantive provider calls:               60 maximum
Exact-route probes:                        2 maximum
Semantic repairs per run:                  1 maximum
Model fallbacks before decisive failure:   2
Whole protected-run cost:               USD 5.00 maximum
```

| Model | Per-call ceiling | Per-model ceiling |
| --- | ---: | ---: |
| GPT-5.6 Sol | USD 0.15 | USD 4.51 |
| Nex N2 Mini | USD 0.01 | USD 0.31 |

These values are retained historical limits, not authority for another run.

## Protected attempt 1

Run `30771922641` at trusted SHA
`dff2f609343be96c76ad646b8e2eaa97ad8e3b3e` passed the exact GPT/OpenAI route probe.
The first corpus call then used 35,806 input tokens, exhausted its output allowance and
cost USD 0.23914375 against the fixed USD 0.12 ceiling.

No second corpus call and no Nex call occurred.

```text
Classification: inconclusive-infrastructure
Protected artifact: 8840792374
Digest: sha256:a0c4d542d6fdfac5cc03a1167aca62da9ab675f40dd7b91618932571f70a3629
```

## Protected attempt 2 — final run

Run `30777564268` at trusted SHA
`40c9fd533dd79bb4b4a6c8bd1f232646bf1f37c5` passed the exact route and secret-free
preparation.

Three complete GPT repeats were retained for one case:

| Repeat | Outcome | Precision | Recall | F1 | Cost |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | Accepted initial | 28.57% | 25.00% | 26.67% | USD 0.1424575 |
| 2 | Deterministic fallback | 0% | 0% | 0% | USD 0.040352 |
| 3 | Accepted initial | 42.86% | 37.50% | 40.00% | USD 0.033482 |

The next exact-route call cost USD 0.15841625 against the fixed USD 0.15 ceiling. It was
persisted before the run failed closed. No later GPT call and no Nex call occurred. Total
reported final-run spend was USD 0.37542275.

```text
Classification: inconclusive-infrastructure
Prepared artifact: 8842553997
Prepared digest: sha256:6b39ca56a84bbdc3dcd63e438fce0b5401e75da95dbeae3c5a3a46f108c72204
Protected artifact: 8842583436
Protected digest: sha256:a40c94efcc7c125026abfc69d942eeb7ae70e210f81c366b4319dcecab7e54c7
```

The three completed rows are diagnostic only and do not constitute a formal Gate A
result.

## Final operational boundary

- Deterministic selection is the sole active selector.
- No bounded model selector is enabled for production or scheduling.
- No further paid Phase 6 run is authorised.
- The paid workflow entry point is archived.
- Automatic generation and publication remain disabled and separately governed.
- Historical implementation and evidence remain retained for audit and research.

A future investigation requires a new phase, reviewed corpus and criteria, realistic
transport calibration, explicit model/provider identities, a new cost plan, stop-loss and
separate authority for paid execution and operational enablement.
