# Governed bounded-selector model comparison

> **Mode:** Reference  
> **Audience:** CryptoPulse developers, reviewers and governance stakeholders  
> **Outcome:** Look up the Phase 6 Slice 6 models, provider policy, call ceilings, scoring rules, artefacts and decision boundary.

## Canonical artefacts

| Artefact | Canonical path |
| --- | --- |
| Comparison configuration | [`config/candidate-selection-model-comparison.yml`](../../config/candidate-selection-model-comparison.yml) |
| Configuration loader | [`llm_analysis/candidate_selection_model_comparison_config.py`](../../llm_analysis/candidate_selection_model_comparison_config.py) |
| OpenRouter selector adapter | [`llm_analysis/openrouter_candidate_selector.py`](../../llm_analysis/openrouter_candidate_selector.py) |
| Protected evaluator | [`llm_analysis/candidate_selection_model_comparison.py`](../../llm_analysis/candidate_selection_model_comparison.py) |
| Scoring and decision rules | [`llm_analysis/candidate_selection_model_scoring.py`](../../llm_analysis/candidate_selection_model_scoring.py) |
| Manual workflow | [`.github/workflows/governed-candidate-selection-model-comparison.yml`](../../.github/workflows/governed-candidate-selection-model-comparison.yml) |
| Evaluation record | [`evaluation/phase-06/candidate-selection-model-comparison/`](../../evaluation/phase-06/candidate-selection-model-comparison/) |
| Permanent tests | [`tests/test_candidate_selection_model_comparison.py`](../../tests/test_candidate_selection_model_comparison.py), [`tests/test_openrouter_candidate_selector.py`](../../tests/test_openrouter_candidate_selector.py) and [`tests/test_governed_candidate_selection_model_comparison_workflow.py`](../../tests/test_governed_candidate_selection_model_comparison_workflow.py) |

This contract implements issue #295. It does not enable a production selector. A
separate reviewed decision is required after the protected comparison.

## Fixed comparison

Only two exact OpenRouter model slugs may receive generation calls:

| Role | Model | Allowed actual provider | Deployment eligible |
| --- | --- | --- | --- |
| Quality upper bound | `openai/gpt-5.6-sol` | `OpenAI` | No |
| Deployment candidate | `nex-agi/nex-n2-mini` | `Nex AGI` | Yes, but only as a future candidate |

Each model receives the same five frozen Slice 3 candidate sets three times. Model
aliases, router aliases, suffix variants and cross-model substitution are prohibited.
The live catalogue and exact route are checked again before corpus calls.

## Responsibility boundary

The model still owns only the choice of existing candidate IDs. Slice 5 remains
responsible for:

- the one-field response schema;
- exact membership, uniqueness and maximum-count checks;
- section, intent, evidence-bundle and redundancy limits;
- one eligible machine-readable repair;
- deterministic fallback;
- canonical plan reconstruction;
- existing claim-plan validation and deterministic rendering.

Slice 6 adds measurement, not semantic authority. It cannot change candidate
compilation, ranking, evidence, values, prose or report publication.

## Secret-free preparation

The prepare command regenerates and verifies the complete deterministic baseline, then
freezes for each case:

- the canonical evidence bundle;
- the complete ordered candidate catalogue;
- the repository-owned selector request;
- the reviewed useful candidate IDs;
- the deterministic selection, plan and rendered Markdown;
- all relevant identities and hashes.

Preparation fails if the retained baseline is not exactly:

```text
Selected candidates:        35
Reviewed-useful selected:   26
Reviewed-useful expected:   38
Precision:                  74.285714%
Recall:                     68.421053%
F1:                         71.232877%
```

No secret is available and no provider call is possible during preparation.

## Protected execution

The workflow is:

- manually dispatched only;
- rejected unless dispatched from `main`;
- prepared from the current trusted-main SHA;
- evaluated from that exact immutable SHA;
- granted `contents: read` only;
- protected by the existing `governed-llm-dry-run` environment;
- unable to create branches, commits, pull requests, reports or site output.

The public-data profile permits only `public-market-data` and `evaluation-only` inputs,
keeps `data_collection: deny`, and uses the explicit public-data `zdr: false`
exception. Raw completions remain protected workflow artefacts.

## Call and cost ceilings

```text
Logical selector runs:           30 maximum
Substantive provider calls:      60 maximum
Exact-route probes:               2 maximum
Semantic repairs per run:         1 maximum
Whole protected-run cost:      USD 4.00 maximum
```

Per-call and per-model ceilings are checked before every request and again after
reported cost is received. Missing cost or token metadata fails closed. Network retry
is disabled inside the adapter, and the comparison pacer permits one transport attempt
per logical provider call, so infrastructure retry cannot silently exceed the 60-call
ceiling.

## Model credit

An accepted first response or accepted repair receives model credit. Deterministic
fallback remains the safe final result but contributes an empty model-selected set:
zero selected candidates, zero useful candidates, zero precision and zero recall.

This prevents the permanent deterministic baseline from inflating model quality.
Failed repeats also contribute an empty set to pairwise stability rather than being
excluded.

## Metrics

Per run, case and model, the evaluator retains:

- first-pass acceptance, repaired acceptance and deterministic fallback;
- useful-candidate precision, recall and F1;
- prohibited and redundant selections;
- exact-repeat rate and pairwise Jaccard stability;
- logical latency;
- input, output and reasoning tokens;
- call, model and total cost;
- requested and actual model/provider identities;
- provider and cross-model fallback evidence;
- canonical plan and rendered-output hashes.

Aggregate quality is micro-averaged over all fifteen logical runs per model. Every
repeat contributes its complete reviewed-useful denominator.

## Predeclared outcomes

The quality upper bound must first clear its acceptance, precision, recall, F1,
stability, safety and governance gates. Failure yields:

```text
remove-model-selector-from-active-roadmap
```

Only when the quality upper bound passes is the deployment candidate assessed against
baseline gaps, uplift retention, stability, latency, cost and governance. Failure or
success yields respectively:

```text
research-only-no-deployment-selector
retain-bounded-selector-candidate
```

An incomplete catalogue, route or corpus produces:

```text
inconclusive-infrastructure
```

The workflow writes deterministic decision input but cannot approve or promote the
result. A separately reviewed issue and pull request must make the Phase 6 decision.

## Artefact retention

Prepared inputs are retained for seven days. Protected outputs are retained for thirty
days and include raw completions, hashes, validations, repairs, fallbacks, per-run
scores, aggregate JSON, reviewer CSV and decision-input Markdown.

Nothing in this workflow is committed or published automatically.
