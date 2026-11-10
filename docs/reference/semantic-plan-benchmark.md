# Semantic claim-plan benchmark

> **Mode:** Reference  
> **Audience:** CryptoPulse operators, reviewers and governance stakeholders  
> **Outcome:** Look up the protected benchmark boundary, retained artefacts and qualification fields for the semantic-plan architecture.

## Canonical workflow and profile

| Artefact | Path or value |
| --- | --- |
| Workflow | [`.github/workflows/governed-gpt4o-mini-public-demo.yml`](../../.github/workflows/governed-gpt4o-mini-public-demo.yml) |
| Runner | [`llm_analysis/semantic_plan_benchmark.py`](../../llm_analysis/semantic_plan_benchmark.py) |
| Semantic profile | [`config/llm-public-data-semantic-plan.yml`](../../config/llm-public-data-semantic-plan.yml) |
| Benchmark model plan | [`config/llm-evaluation-gpt-4o-mini-semantic-plan.yml`](../../config/llm-evaluation-gpt-4o-mini-semantic-plan.yml) |
| Model | `openai/gpt-4o-mini` |
| Corpus | five frozen cases, two repeats per case |

The historical natural-prose profile, runner and reviewed decision remain unchanged. The semantic profile overlays only the claim-plan prompt, schema and renderer contract on the existing public-data policy, model, corpus and cost limits.

## Execution boundary

```text
Manual workflow_dispatch from trusted main
        ↓
Public/evaluation-only corpus classification
        ↓
Exact trusted main SHA + deterministic evidence bundles
        ↓
OpenRouter route preflight
        ↓
10 semantic claim-plan generations
        ↓
Canonical claim-plan validation
        ↓
Repository-owned deterministic rendering
        ↓
Non-published protected workflow artefact
```

The workflow has `contents: read`, receives the provider secret only in the protected evaluation job and has no pull-request, repository-write, schedule or publication capability.

## Preserved policy

```text
Allowed inputs:                  public-market-data | evaluation-only
Default production ZDR path:     unchanged
Protected public-data ZDR:       false under the existing explicit exception
Data collection:                 deny
Cross-model fallback:            disabled
Per-generation cost ceiling:     USD 0.01
Whole-run cost ceiling:          USD 0.15
Automatic generation:            disabled
Publication:                     disabled
```

## Per-run artefacts

Each corpus run retains:

| File | Contents |
| --- | --- |
| `provider-completion.raw.json` | Exact provider completion text; workflow artefact only. |
| `canonical-claim-plan.json` | Canonical JSON representation of the returned semantic plan. |
| `claim-plan-validation.json` | Ordered schema, referential, semantic and policy diagnostics. |
| `rendered-analysis.md` | Repository-owned deterministic output when the plan passes. |
| `rendered-claims.json` | Structured claim, intent, evidence-ID and generated-sentence grounding. |
| `semantic-provenance.json` | Hash links across evidence, provider completion, plan, validation, renderer and final output. |
| `generation-metadata.json` | Secret-free provider, usage, routing and request metadata. |
| `run-record.json` | Separate plan, rendering, injection, disagreement, identity, fallback and cost outcomes. |

Raw completion text is uploaded with the protected artefact and is never copied into source control.

## Qualification fields

A run qualifies only when the aggregate summary records:

```text
Validated claim plans:                  10 / 10
Validated rendered outputs:             10 / 10
Byte-identical rerenders:               10 / 10
Prompt-injection safety:                 2 / 2
Source-disagreement valid or silent:     2 / 2
Exact requested/actual model identity:   true
Actual provider identity complete:       true
Cross-model fallback runs:               0
Policy failures:                         0
Cost metadata complete:                  true
Whole-run cost:                          <= USD 0.15
Automatic generation:                    false
Publication:                             false
```

The runner reports `semantic-plan-qualified` or `semantic-plan-no-go`. It does not publish or create a rolling market-analysis pull request.

## Provenance chain

`semantic-provenance.json` binds:

```text
evidence bundle ID and SHA-256
source snapshot path and SHA-256
raw completion SHA-256 and generation ID
claim-plan schema/prompt versions and SHA-256
validation report SHA-256
renderer version
rendered output SHA-256
requested/actual model and provider
provider and cross-model fallback state
tokens, latency and cost
input classification and public-data policy
```

This allows review to establish grounding without extracting facts back out of final prose.
