# Phase 7 low-cost candidate-selector Stage 0

Status: complete and archived.

This directory documents the one-run compatibility and cost screen governed by #314,
#315, #317 and #321. No provider output is committed here.

## Protected execution

```text
Run:          30780938812
Event:        issue_comment
Trusted SHA:  c5e22c35ab23d0ff43b0801e2d1675216d5cbc2b
Created:      2026-08-03T03:06:29Z
Completed:    2026-08-03T03:07:08Z
Conclusion:   success
```

Workflow success means the governed screen completed and retained its classifications.
It does not mean a model was compatible.

No second Stage 0 run is authorised. The paid workflow was removed after the protected
evidence was retained.

## Fixed input

The screen regenerated the Phase 6 `historical-degraded-sparse` case and its complete
candidate catalogue.

```text
Candidates:            201
Compact request bytes: 46,022
Compact request ID:    sha256:7ecd536db61a99a33eea0a90cc667935c381d58ff93684bbc953eb0c4b308ce0
```

The provider-visible request was the retained compact projection of the real canonical
selector request. It was not a toy prompt, a shortlist or a post-hoc modification.

## Results

| Model | Approved provider | Classification | Selector generations | Governed cost |
| --- | --- | --- | ---: | ---: |
| `deepseek/deepseek-v4-flash-0731` | `DeepSeek` | `route-ineligible` | 0 | USD 0.005 |
| `openai/gpt-oss-120b` | `DeepInfra` | `inconclusive-infrastructure` | 0 | USD 0.005 |
| `inception/mercury-2` | `Inception` | `inconclusive-infrastructure` | 0 | USD 0.010 |

DeepSeek had no exact endpoint able to satisfy the reviewed parameter set and provider
lock. GPT-OSS and Mercury route probes did not contain usable `message.content`; their
route evidence was incomplete and the reviewed maximum was reserved.

```text
Route probes:          3
Selector generations:  0
Paid-call ledger:      3
Reserved total cost:   USD 0.020
Compatible models:     0
Semantic repairs:      0
Network retries:       0
```

Because no selector generation occurred, the screen contains no model selection,
candidate usefulness, reconstruction, rendering, token, latency or output-validity
result. In particular, the two infrastructure-inconclusive classifications are not
model-quality failures.

## Catalogue evidence

All three model catalogue entries were available, inside the configured catalogue-price
caps and advertised both `response_format` and `structured_outputs` when checked during
the run. Catalogue support did not prove that the exact provider route could satisfy the
reviewed request.

## Retained artefacts

Prepared input:

```text
Artifact ID: 8843606111
Digest: sha256:a25004953c6fa46bc40157a7dc1cca482c1d3f8210c376235892c2ec6b7e387e
```

Protected evidence:

```text
Artifact ID: 8843610508
Digest: sha256:416171e18ea8ef5253dbc7154b7df58f6dbba7fe8f0ca1c7dad0340fcce64c91
```

The protected evidence contains the exact trusted SHA, current catalogue records,
route records, reserved metering, model classifications and machine-readable summary.
No selector completion was produced.

## Preserved boundaries

```text
stage1_authorized: false
winner_selected: false
automatic_generation: false
publication: false
repository_write: false
```

The deterministic Phase 6 selector remains the sole active selector. A future model
screen requires a new reviewed issue, provider-route design, budget and explicit
authority. It cannot reuse this workflow, nonce or paid-run approval.
