# Observable OpenRouter transport calibration

> **Mode:** Reference  
> **Audience:** CryptoPulse developers, reviewers and governance stakeholders  
> **Outcome:** Look up the completed Phase 8 real-request discovery and pinned-provider reproduction evidence.  
> **Status:** Historical; protected run complete and paid workflow archived

## Decision question

> Can at least one model complete the real candidate-ID request under an observable, realistically configured route?

**Yes.** Protected run `30784874599` demonstrated that `openai/gpt-oss-120b` could complete the real 201-candidate request through DeepInfra and then reproduce successfully with canonical provider slug `deepinfra` pinned and fallbacks disabled.

This is transport-operability evidence only. It does not reopen the Phase 6 quality decision, approve a model selector, establish full-corpus quality or enable report generation or publication.

## Why Phase 8 existed

The Phase 7 route probe allowed only 16 output tokens and required final `message.content` before retaining the complete response. Reasoning-capable models could therefore be rejected without preserving whether the response contained reasoning, a length finish, usage, cost or router metadata.

Phase 8 removed that generated toy probe. The first paid request was the real compact 201-candidate selector request, and every HTTP response was retained before interpretation.

## Protected execution

```text
Run:                       30784874599
Trusted SHA:               6db61d5307a51ba04507c29d39ea72f026b7d9fc
Candidate count:           201
Compact request bytes:     46,022
Discovery calls:           2
Reproduction calls:        1
Paid calls:                3
Total reported cost:       USD 0.007966518
Semantic repairs:          0
Network retries:           0
```

### Mercury 2 discovery

```text
Model:             inception/mercury-2
Provider:          Inception
Classification:    invalid-json-content
Input tokens:      19,012
Output tokens:     1,971
Reasoning tokens:  1,957
Finish reason:     length
Cost:              USD 0.00616555
```

The response retained only the incomplete prefix `{"selected_candidate_ids":` because reasoning consumed nearly the full 2,048-token output allowance. This provides direct evidence that the earlier 16-token generated probe was unsuitable for this reasoning model. It does not establish that Mercury cannot perform the task under a different reasoning/output configuration.

### GPT-OSS discovery

```text
Model:             openai/gpt-oss-120b
Provider:          DeepInfra
Provider slug:     deepinfra
Classification:    completed
Input tokens:      19,242
Output tokens:     1,109
Reasoning tokens:  628
Finish reason:     stop
Cost:              USD 0.000900484
Selected IDs:      7
```

All seven IDs passed the existing candidate-selection contract, canonical reconstruction, claim-plan validation and deterministic rendering boundary.

### GPT-OSS pinned reproduction

The identical real request was repeated with:

```text
provider.only: [deepinfra]
allow_fallbacks: false
```

The reproduction completed at the same reported cost and produced the same seven IDs, the same claim-plan hash and the same rendered Markdown hash:

```text
Claim-plan SHA-256:        2575f2e6d1ff6c6960f052b5b3f2af783f80fd9f9c7cbd4b6812b889459ebe9b
Rendered Markdown SHA-256: 0f4eb1f0b187db1d4645ac2dc2088de9a993242cdf98bf1ee0c25d8a740c96aa
```

This is useful reproduction evidence but remains only two calls on one frozen case. It does not establish aggregate quality, stability or incremental value against the deterministic selector.

## Retained artifacts

```text
Prepared artifact: 8844907236
Digest: sha256:14c8560c565c49547e5e32fa88f5d7c9ca32c98d337b3009b7c30c7401ca0f7d

Protected artifact: 8844924119
Digest: sha256:ac3af0e5e825d21cdf62f7266d6db3342514ae35437a4e1015de6d128a1ab295
```

The protected artifact contains request hashes, HTTP observations, raw response bodies, router metadata, usage, cost, validation diagnostics, selections, reconstructed plans and deterministic renders.

## Archived execution boundary

The temporary paid workflow has been removed from `main`. There is **no rerun** authorised under Phase 8. The configuration, runner, tests and historical evidence references remain retained for audit or a separately governed quality comparison.

The deterministic Phase 6 selector remains the sole active selector. Automatic generation, scheduling, repository writes and publication remain disabled.