# Phase 6 bounded candidate-selection model comparison

This directory documents the protected Slice 6 comparison governed by #295 and the
provider-transport correction governed by #300. No provider output is committed here.
Prepared inputs are retained for seven days and protected outputs for thirty days as
GitHub Actions artefacts.

## Fixed comparison

| Role | Exact model | Actual provider | Cases | Repeats | Output cap |
| --- | --- | --- | ---: | ---: | ---: |
| Quality upper bound | `openai/gpt-5.6-sol` | `OpenAI` | 5 | 3 | 1,024 |
| Deployment candidate | `nex-agi/nex-n2-mini` | `Nex AGI` | 5 | 3 | 512 |

The deterministic Slice 4 selector is regenerated once per case and remains the
comparison baseline and Slice 5 operational fallback. Fallback keeps the final plan
valid but gives the model zero candidate-quality credit.

## Compact transport

The complete canonical request and candidate set remain repository-owned. The provider
receives a versioned positional projection with every full candidate ID and the bounded
editorial fields needed for selection, but without evidence IDs, source prose or
repeated verbose property names.

Secret-free preparation proves that the compact projection preserves the exact ordered
ID set and remains below 65,536 bytes for every frozen case. Current compact sizes range
from 45,174 to 51,320 bytes for 201–230 candidates, compared with 125,714 to 142,678
bytes for the canonical requests.

## Protected artefacts

The workflow retains:

- the exact trusted-main SHA and checked-in comparison configuration;
- frozen evidence bundles, canonical candidate catalogues and selector requests;
- compact request identities, field/code legends and projected catalogues;
- reviewed useful IDs and regenerated deterministic selections, plans and Markdown;
- live catalogue and exact-route evidence;
- raw model completions, hashes, diagnostics, repairs and fallbacks;
- requested and actual model/provider identities;
- latency, token and cost evidence;
- per-run scores, aggregate summaries, reviewer CSV and deterministic decision input.

Every metered provider response is written before model-output validation. A networked
selector call or route probe without trustworthy usage/cost reserves the full reviewed
per-call ceiling, retains sanitised failure evidence and stops as
infrastructure-inconclusive.

## Corrective calibration

Protected run `30771922641` validated the exact GPT/OpenAI route but showed the original
transport was not viable. The first corpus request used 35,806 input tokens, exhausted
the 512-token output budget and cost USD 0.23914375. The run was recorded as
infrastructure-inconclusive and produced no model-quality conclusion.

The correction uses the compact projection, raises only the GPT output cap to 1,024,
sets reviewed ceilings of USD 0.15 per GPT call, USD 4.51 per GPT model run, USD 0.01
per Nex call, USD 0.31 per Nex model run and USD 5.00 overall, and adds decisive early
stopping after two fully metered model fallbacks.

## Reproduce the secret-free preparation

```bash
python -m llm_analysis.candidate_selection_model_comparison_runner prepare \
  --repository-root . \
  --config config/candidate-selection-model-comparison.yml \
  --output-dir /tmp/candidate-selection-model-comparison-prepared
```

Preparation makes no provider call. It fails if the frozen corpus, reviewed candidate
IDs, deterministic ranking policy, baseline metrics or compact projection contract have
drifted.

## Protected execution

The workflow is manual-only, trusted-main, read-only and uses the
`governed-llm-dry-run` environment. It invokes the fail-closed protected runner and
cannot modify repository state, publish a report or promote a model.

After two fully metered fallbacks, a model can no longer meet the 14/15 acceptance gate:
quality-model failure skips Nex and yields `remove-model-selector-from-active-roadmap`;
deployment-candidate failure yields `research-only-no-deployment-selector`.
Infrastructure failures remain `inconclusive-infrastructure`.

A separate reviewed issue and pull request must interpret the retained decision input.
