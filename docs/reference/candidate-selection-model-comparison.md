# Governed bounded-selector model comparison

> **Mode:** Reference  
> **Audience:** CryptoPulse developers, reviewers and governance stakeholders  
> **Outcome:** Look up the Phase 6 Slice 6 models, compact provider transport, cost ceilings, scoring rules, artefacts and decision boundary.

## Canonical artefacts

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
| Manual workflow | [`.github/workflows/governed-candidate-selection-model-comparison.yml`](../../.github/workflows/governed-candidate-selection-model-comparison.yml) |
| Evaluation record | [`evaluation/phase-06/candidate-selection-model-comparison/`](../../evaluation/phase-06/candidate-selection-model-comparison/) |

This contract implements issue #295 and corrective issue #300. It does not enable a
production selector. A separate reviewed decision is required after the protected run.

## Fixed comparison

| Role | Model | Allowed actual provider | Repeats | Output cap |
| --- | --- | --- | ---: | ---: |
| Quality upper bound | `openai/gpt-5.6-sol` | `OpenAI` | 3 per case | 1,024 tokens |
| Deployment candidate | `nex-agi/nex-n2-mini` | `Nex AGI` | 3 per case | 512 tokens |

Each model receives the same five frozen Slice 3 candidate sets. Model aliases, router
aliases, provider substitution and cross-model fallback are prohibited. The live
catalogue and exact route are checked before corpus calls.

## Responsibility boundary

The model still owns only the choice of existing candidate IDs. Slice 5 remains the
authority for exact membership, uniqueness, count, section, intent, bundle and
redundancy validation, one eligible repair, deterministic fallback, canonical plan
reconstruction, validation and rendering.

The compact projection is provider transport only. It cannot remove candidates, alter
candidate IDs, change canonical ordering or weaken repository validation.

## Compact provider request

Repository records retain the complete canonical selector request. For provider
transport, each candidate is projected into one positional row containing:

```text
candidate_id, section, intent, subject type, subject id, metric, confidence,
comparison relation, materiality, conflict status, quality significance,
cross-source flag, corroboration count, recency and redundancy group
```

The request contains explicit field and enum-code legends and the unchanged canonical
request ID. Evidence IDs, source prose and verbose repeated property names are omitted.
The full canonical candidate ID remains in every row and is the only value the model may
return.

Secret-free preparation verifies the exact ordered ID set and a maximum of 65,536 bytes
per compact request. The frozen cases currently produce:

| Case | Canonical bytes | Compact bytes | Candidates |
| --- | ---: | ---: | ---: |
| Historical degraded/sparse | 125,714 | 45,174 | 201 |
| Historical normal/cross-checked | 142,248 | 50,891 | 229 |
| Historical material move | 142,678 | 51,320 | 230 |
| Adversarial prompt injection | 138,531 | 49,898 | 225 |
| Adversarial source disagreement | 137,419 | 49,693 | 224 |

## Baseline and model credit

Preparation regenerates the permanent deterministic comparator:

```text
Selected candidates:        35
Reviewed-useful selected:   26
Reviewed-useful expected:   38
Precision:                  74.285714%
Recall:                     68.421053%
F1:                         71.232877%
```

A first-pass or repaired accepted ID list receives model credit. Deterministic fallback
remains the safe final output but contributes an empty model selection: zero selected,
zero useful, zero precision and zero recall. Failed repeats remain in stability and
aggregate recall rather than being excluded.

## Protected execution

The workflow is manual-only, trusted-main, exact-SHA, `contents: read`, protected by the
existing `governed-llm-dry-run` environment and unable to write repository state or
publish reports. It permits only public-market and evaluation-only inputs, retains
`data_collection: deny` and uses the explicit public-data `zdr: false` exception.

Every metered selector response is persisted and charged before content, model or
provider validation. An unmetered networked selector call or route probe retains a
sanitised failure record, reserves the full reviewed call ceiling and aborts as
infrastructure-inconclusive. Provider fallback, model/provider substitution and over-cap
cost are retained before aborting. Correctly routed malformed JSON remains a metered
model failure and enters deterministic fallback.

## Call and cost ceilings

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

Budget checks occur before every request and after reported cost. Network retry is
disabled and only one transport attempt is allowed per logical provider call.

## Decisive early stopping

Both model gates require at least 14 accepted runs out of 15. After two fully metered
model fallbacks, that model cannot pass the acceptance gate.

- Two quality-model fallbacks stop the comparison and yield
  `remove-model-selector-from-active-roadmap`; Nex is not called.
- Two deployment-candidate fallbacks yield
  `research-only-no-deployment-selector`.
- Catalogue, route, identity, metering, policy or other infrastructure failures remain
  `inconclusive-infrastructure` and are never converted into model-quality failure.

A complete passing comparison may yield `retain-bounded-selector-candidate`, but the
workflow cannot promote or enable the model. A separately reviewed decision issue and
pull request remain mandatory.

## Calibration history

Protected run `30771922641` validated the exact OpenAI route but showed that the original
full JSON transport was not viable: the first corpus request used 35,806 input tokens,
reached the 512-token completion cap and cost USD 0.23914375. It was recorded as
infrastructure-inconclusive. The compact projection, model-specific output cap, revised
ceilings and decisive stop are the reviewed corrective response; the run is not treated
as model-quality evidence.

## Artefact retention

Prepared inputs are retained for seven days. Protected outputs are retained for thirty
days and include canonical and compact request identities, raw completions, hashes,
validations, repairs, fallbacks, per-run scores, aggregate JSON, reviewer CSV and
decision-input Markdown. Nothing is committed or published automatically.
