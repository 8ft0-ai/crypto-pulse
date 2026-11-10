# Low-cost candidate-selector Stage 0

> **Mode:** Reference  
> **Audience:** CryptoPulse developers, reviewers and governance stakeholders  
> **Outcome:** Look up the completed Phase 7 Stage 0 contract, protected result and archival boundary.

## Status

Phase 7 Stage 0 is complete as a one-run compatibility and cost screen governed by
issues #314, #315, #317 and #321.

Protected run `30780938812` executed at trusted commit
`c5e22c35ab23d0ff43b0801e2d1675216d5cbc2b`. The temporary paid workflow was removed
after evidence retention. No second Stage 0 run is authorised.

The run did not approve Stage 1, choose a winner or enable a model selector. The
deterministic Phase 6 selector remains the sole active selector.

## Retained implementation

| Artefact | Path |
| --- | --- |
| Stage 0 configuration | [`config/low-cost-candidate-selector-stage-0.yml`](../../config/low-cost-candidate-selector-stage-0.yml) |
| Strict configuration loader | [`llm_analysis/candidate_selector_stage0_config.py`](../../llm_analysis/candidate_selector_stage0_config.py) |
| Preparation and execution | [`llm_analysis/candidate_selector_stage0.py`](../../llm_analysis/candidate_selector_stage0.py) |
| Protected CLI | [`llm_analysis/candidate_selector_stage0_runner.py`](../../llm_analysis/candidate_selector_stage0_runner.py) |
| Evaluation record | [`evaluation/phase-07/low-cost-selector-stage-0/`](../../evaluation/phase-07/low-cost-selector-stage-0/) |

The former workflow path was:

```text
.github/workflows/governed-low-cost-selector-stage-0.yml
```

It is intentionally absent from `main`. Git history preserves its reviewed read-only,
trusted-main and protected-environment implementation.

## Fixed models

| Model | Approved provider | Stage 0 result |
| --- | --- | --- |
| `deepseek/deepseek-v4-flash-0731` | `DeepSeek` | `route-ineligible` |
| `openai/gpt-oss-120b` | `DeepInfra` | `inconclusive-infrastructure` |
| `inception/mercury-2` | `Inception` | `inconclusive-infrastructure` |

All three catalogue records were available and inside the reviewed catalogue-price
caps when checked on 2026-08-03. Each advertised both `response_format` and
`structured_outputs`.

The route results were:

- DeepSeek V4 Flash 0731: no endpoint could satisfy the exact reviewed parameters and
  provider lock;
- GPT-OSS 120B: the route probe returned without usable `message.content`;
- Mercury 2: the route probe returned without usable `message.content`.

No model reached the real selector generation. Therefore Stage 0 contains no
candidate-selection quality, latency, token or validity result for any model.

## Real request boundary

Secret-free preparation regenerated the Phase 6 `historical-degraded-sparse` case from
trusted repository inputs. The case contained 201 candidates.

```text
Candidate count:       201
Compact request bytes: 46,022
Compact request ID:    sha256:7ecd536db61a99a33eea0a90cc667935c381d58ff93684bbc953eb0c4b308ce0
```

The compact projection retained every full candidate ID in canonical order, the
canonical request identity, bounded editorial fields and the existing selection limits.
No toy shortlist or post-hoc candidate filtering was used.

## Reviewed execution boundary

Each model was permitted:

```text
exact-route probes:       1 maximum
selector generations:     1 maximum
semantic repairs:         0
network retries:          0
provider fallback:        false
cross-model fallback:     false
```

The whole screen permitted three route probes, three selector generations, six paid
calls and a USD 0.060 ceiling.

The run completed with:

```text
Route probes:          3
Selector generations:  0
Paid-call ledger:      3
Reserved total cost:   USD 0.020
Semantic repairs:      0
Network retries:       0
Compatible models:     0
```

The ledger reserved the reviewed route ceiling whenever trustworthy usage or cost was
not available. The USD 0.020 value is therefore the governed accounting amount, not a
claim that OpenRouter necessarily charged exactly that amount.

## Provider policy

Every route and selector request was configured with:

```json
{
  "require_parameters": true,
  "data_collection": "deny",
  "zdr": false,
  "allow_fallbacks": false,
  "only": ["one reviewed provider"]
}
```

The explicit `zdr: false` exception applied only to the existing public-market and
evaluation-only input profile. Customer, personal, credential, internal, confidential
and sensitive inputs remained prohibited.

## Stage 0 classifications

| Classification | Meaning |
| --- | --- |
| `compatible` | Exact metered route completed within budget and the existing selection, reconstruction, validation and rendering boundary passed. |
| `route-ineligible` | No eligible exact provider route existed before the selector call. |
| `schema-incompatible` | The route rejected or ignored the strict structured-output contract. |
| `identity-failure` | The actual model or provider differed from the reviewed identity, or fallback occurred. |
| `cost-ineligible` | Catalogue or observed cost exceeded a reviewed ceiling. |
| `inconclusive-infrastructure` | Route, usage or cost evidence was insufficient for another classification. |
| `model-output-invalid` | The exact metered route completed, but its single candidate-ID response failed the existing contract. |

A route-level `inconclusive-infrastructure` result is not model-quality evidence. It
must not be interpreted as a failed candidate selection.

## Protected evidence

Prepared input artefact:

```text
Artifact ID: 8843606111
Digest: sha256:a25004953c6fa46bc40157a7dc1cca482c1d3f8210c376235892c2ec6b7e387e
Retention: 7 days from 2026-08-03
```

Protected result artefact:

```text
Artifact ID: 8843610508
Digest: sha256:416171e18ea8ef5253dbc7154b7df58f6dbba7fe8f0ca1c7dad0340fcce64c91
Retention: 30 days from 2026-08-03
```

The protected result retains catalogue checks, route records, trusted SHA, compact
request identity, classifications and the machine-readable summary. No raw provider
selection completion exists because no selector generation occurred.

## Permanent decision boundary

The Stage 0 result records:

```text
stage1_authorized: false
winner_selected: false
automatic_generation: false
publication: false
repository_write: false
```

No Stage 1 run follows automatically. A future low-cost model investigation requires a
newly reviewed model/provider route plan, explicit execution budget and separate
repository-owner authority. It must not reuse the completed Stage 0 nonce or workflow.
