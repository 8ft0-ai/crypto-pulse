# Phase 8 observable OpenRouter transport calibration

This directory records the completed transport-calibration contract and protected evidence identities governed by issues #325, #327 and #331. Provider responses remain protected GitHub Actions artifacts and are not committed here.

## Question and answer

> Can at least one model complete the real candidate-ID request under an observable, realistically configured route?

**Yes.** `openai/gpt-oss-120b` completed discovery through DeepInfra and completed reproduction with canonical provider slug `deepinfra` pinned and fallbacks disabled.

## Frozen request

```text
Case:                   historical-degraded-sparse
Candidate count:        201
Compact request bytes:  46,022
Compact request ID:     sha256:7ecd536db61a99a33eea0a90cc667935c381d58ff93684bbc953eb0c4b308ce0
```

The response remained the existing one-field `selected_candidate_ids` envelope, with repository-owned validation, reconstruction and deterministic rendering. There was no preliminary generated route probe.

## Protected run

```text
Run:                       30784874599
Trusted SHA:               6db61d5307a51ba04507c29d39ea72f026b7d9fc
Discovery calls:           2
Reproduction calls:        1
Paid calls:                3
Total reported cost:       USD 0.007966518
Semantic repairs:          0
Network retries:           0
Model selector enabled:    false
Automatic generation:      false
Publication:               false
Repository write:          false
```

## Call results

| Stage | Model | Provider | Classification | Finish | Reasoning/output tokens | Cost |
| --- | --- | --- | --- | --- | ---: | ---: |
| discovery | `inception/mercury-2` | `Inception` | `invalid-json-content` | `length` | 1,957 / 1,971 | USD 0.00616555 |
| discovery | `openai/gpt-oss-120b` | `DeepInfra` | `completed` | `stop` | 628 / 1,109 | USD 0.000900484 |
| reproduction | `openai/gpt-oss-120b` | pinned `deepinfra` | `completed` | `stop` | 628 / 1,109 | USD 0.000900484 |

Mercury retained only an incomplete JSON prefix after reasoning consumed nearly all available output tokens. GPT-OSS returned seven valid candidate IDs in both calls. Both GPT calls produced:

```text
Claim-plan SHA-256:        2575f2e6d1ff6c6960f052b5b3f2af783f80fd9f9c7cbd4b6812b889459ebe9b
Rendered Markdown SHA-256: 0f4eb1f0b187db1d4645ac2dc2088de9a993242cdf98bf1ee0c25d8a740c96aa
```

## Protected artifacts

```text
Prepared artifact: 8844907236
Digest: sha256:14c8560c565c49547e5e32fa88f5d7c9ca32c98d337b3009b7c30c7401ca0f7d

Protected artifact: 8844924119
Digest: sha256:ac3af0e5e825d21cdf62f7266d6db3342514ae35437a4e1015de6d128a1ab295
```

The protected artifact retains raw HTTP observations before interpretation, router-selected provider metadata, request and response hashes, usage and cost, model output, selection validation, reconstructed plans and deterministic renders.

## Interpretation boundary

The result proves transport operability for one GPT-OSS/DeepInfra route. The identical outputs provide a small reproduction signal, but two calls on one case do not establish candidate-selection quality, repeat stability, incremental value or production suitability.

The deterministic Phase 6 selector remains the sole active selector. The paid Phase 8 workflow is archived and there is **no rerun** authorised. Any quality comparison requires a new reviewed issue, fixed corpus, decision gate, budget and explicit execution authority.