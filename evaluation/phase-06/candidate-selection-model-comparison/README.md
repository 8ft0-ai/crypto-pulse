# Phase 6 bounded candidate-selection model comparison

This directory documents the protected Slice 6 comparison governed by issue #295.
No provider output is committed here. The workflow retains prepared inputs for seven
days and protected comparison outputs for thirty days as GitHub Actions artefacts.

## Fixed comparison

| Role | Exact model | Actual provider | Cases | Repeats |
| --- | --- | --- | ---: | ---: |
| Quality upper bound | `openai/gpt-5.6-sol` | `OpenAI` | 5 | 3 |
| Deployment candidate | `nex-agi/nex-n2-mini` | `Nex AGI` | 5 | 3 |

The deterministic Slice 4 selector is regenerated once per case and remains both the
comparison baseline and the Slice 5 operational fallback. A fallback keeps the final
plan valid but gives the model zero candidate-quality credit.

## Protected artefacts

The workflow retains:

- the exact trusted-main SHA and checked-in comparison configuration;
- frozen evidence bundles, candidate catalogues, selector requests and reviewed useful IDs;
- regenerated deterministic selections, plans and Markdown;
- live catalogue and exact-route evidence;
- raw model completions, completion hashes and bounded selector diagnostics;
- repair and fallback records;
- requested and actual model/provider identities;
- latency, token and cost evidence;
- per-run scores, aggregate summaries, reviewer CSV and deterministic decision input.

Raw completions and generated reports are workflow artefacts only. They are never
committed, published or copied into `_site/`.

## Reproduce the secret-free preparation

```bash
python -m llm_analysis.candidate_selection_model_comparison prepare \
  --repository-root . \
  --config config/candidate-selection-model-comparison.yml \
  --output-dir /tmp/candidate-selection-model-comparison-prepared
```

Preparation makes no provider call. It fails if the frozen corpus, reviewed candidate
IDs, deterministic ranking policy or retained baseline metrics have drifted.

## Protected execution

The workflow `Governed candidate selection model comparison` is manual-only,
trusted-main, read-only and uses the `governed-llm-dry-run` environment. It cannot
modify repository state or publish a report.

A separate reviewed issue and pull request must interpret the retained decision input.
The protected run cannot promote a model automatically.
