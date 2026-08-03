# Low-cost candidate-selector Stage 0

> **Mode:** Reference  
> **Audience:** CryptoPulse developers, reviewers and governance stakeholders  
> **Outcome:** Look up the Phase 7 Stage 0 models, request, routing controls, cost ceilings, classifications and evidence boundary.

## Status

Phase 7 Stage 0 is a compatibility and cost screen governed by issues #314 and #315.
It does not reopen Phase 6, enable model selection, choose a winner or authorise the
five-case Stage 1 comparison.

The deterministic Phase 6 selector remains the sole active selector throughout this
screen.

## Canonical artefacts

| Artefact | Path |
| --- | --- |
| Stage 0 configuration | [`config/low-cost-candidate-selector-stage-0.yml`](../../config/low-cost-candidate-selector-stage-0.yml) |
| Strict configuration loader | [`llm_analysis/candidate_selector_stage0_config.py`](../../llm_analysis/candidate_selector_stage0_config.py) |
| Preparation and execution | [`llm_analysis/candidate_selector_stage0.py`](../../llm_analysis/candidate_selector_stage0.py) |
| Protected CLI | [`llm_analysis/candidate_selector_stage0_runner.py`](../../llm_analysis/candidate_selector_stage0_runner.py) |
| Temporary workflow | [`.github/workflows/governed-low-cost-selector-stage-0.yml`](../../.github/workflows/governed-low-cost-selector-stage-0.yml) |
| Evaluation record | [`evaluation/phase-07/low-cost-selector-stage-0/`](../../evaluation/phase-07/low-cost-selector-stage-0/) |

## Fixed models

| Model | Approved provider | Role |
| --- | --- | --- |
| `deepseek/deepseek-v4-flash-0731` | `DeepSeek` | primary quality/cost candidate |
| `openai/gpt-oss-120b` | `DeepInfra` | lowest-cost serious control |
| `inception/mercury-2` | `Inception` | low-latency single-provider control |

The current OpenRouter catalogue must still advertise `response_format` and
`structured_outputs` at execution time. Each request pins one reviewed provider.
Provider fallback, model fallback and aliases are prohibited.

## Real request boundary

Secret-free preparation regenerates the Phase 6 `historical-degraded-sparse` case from
trusted repository inputs. The case contains 201 candidates.

The provider receives the retained compact projection rather than a toy prompt or a
post-hoc shortlist. The projection preserves:

- every complete candidate ID;
- canonical candidate ordering;
- the canonical request identity;
- bounded editorial fields and feature codes;
- the existing maximum selection count and section/intent limits.

Evidence IDs, source prose and free-form rationale remain outside the provider request.
Repository validation continues to use the complete canonical candidate catalogue.

## Call boundary

Each model may receive:

```text
exact-route probes:       1 maximum
selector generations:     1 maximum
semantic repairs:         0
network retries:          0
provider fallback:        false
cross-model fallback:     false
```

Whole-screen maxima are three route probes, three selector generations and six paid
calls.

The route probe uses a minimal strict schema. A route must preserve the requested model,
resolve to the approved provider, satisfy required parameters and report trustworthy
cost before the real selector call is allowed.

## Provider policy

Every route and selector request uses:

```json
{
  "require_parameters": true,
  "data_collection": "deny",
  "zdr": false,
  "allow_fallbacks": false,
  "only": ["one reviewed provider"]
}
```

The explicit `zdr: false` exception applies only to the existing public-market and
evaluation-only input profile. Customer, personal, credential, internal, confidential
and sensitive inputs remain prohibited.

The selector response format is strict JSON Schema and contains one property only:

```json
{
  "selected_candidate_ids": [
    "claim-candidate:sha256:..."
  ]
}
```

## Cost ceilings

```text
DeepSeek V4 Flash route + selector: USD 0.015
GPT-OSS 120B route + selector:      USD 0.015
Mercury 2 route + selector:         USD 0.030
Whole Stage 0:                       USD 0.060
```

Budget checks run before calls and after observed cost. A networked response without
trustworthy usage or cost reserves the reviewed call ceiling and stops that model.
Metered responses are persisted and charged before model identity, provider identity or
selection validation.

## Classifications

Each model receives one terminal Stage 0 classification:

| Classification | Meaning |
| --- | --- |
| `compatible` | Exact metered route completed within budget and the existing selection, reconstruction, validation and rendering boundary passed. |
| `route-ineligible` | No eligible exact provider route existed before the selector call. |
| `schema-incompatible` | The route rejected or ignored the strict structured-output contract. |
| `identity-failure` | The actual model or provider differed from the reviewed identity, or fallback occurred. |
| `cost-ineligible` | Catalogue or observed cost exceeded a reviewed ceiling. |
| `inconclusive-infrastructure` | Route, usage or cost evidence was insufficient for another classification. |
| `model-output-invalid` | The exact metered route completed, but its single candidate-ID response failed the existing contract. |

A compatible result is not a quality conclusion. One response cannot establish repeat
stability, corpus recall, incremental value or production suitability. An invalid result
receives no repair in Stage 0.

## Retained evidence

The protected workflow retains:

- trusted-main SHA;
- current catalogue eligibility;
- route evidence and actual provider/model identity;
- canonical and compact request identities;
- provider request and completion hashes;
- raw completion;
- input, output and reasoning tokens;
- latency and cost;
- selection diagnostics;
- reconstructed plan and rendered-output hashes for compatible responses;
- machine-readable model results and a reviewer-readable summary.

Raw provider output remains a protected Actions artefact. It is not committed, rendered
on the public site or used to change repository state.

## Decision boundary

The workflow always records:

```text
stage1_authorized: false
winner_selected: false
automatic_generation: false
publication: false
repository_write: false
```

After the one protected run, the temporary paid workflow must be deleted through a
separate reviewed pull request. A separate reviewed decision may then identify which
models, if any, are eligible for a newly budgeted Stage 1 comparison.
