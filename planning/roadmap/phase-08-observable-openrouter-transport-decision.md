# Phase 8 — Observable OpenRouter transport decision

Status: approved.  
Decision date: 2026-08-03.  
Decision issue: #333  
Phase contract: #325  
Dispatch authority: #327

## Decision

The Phase 8 decision question is answered **yes**:

> Can at least one model complete the real candidate-ID request under an observable, realistically configured route?

`openai/gpt-oss-120b` completed the real 201-candidate request through DeepInfra and then completed an identical reproduction with canonical provider slug `deepinfra` pinned and provider fallback disabled.

This result makes the exact GPT-OSS/DeepInfra route technically eligible for a future, separately governed quality comparison. It does **not** approve or enable a model selector, establish model quality, alter deterministic ranking or authorise production, scheduling, automatic generation or publication.

The deterministic Phase 6 selector remains the sole active candidate-selection path.

## Protected execution

```text
Run:                       30784874599
Trusted SHA:               6db61d5307a51ba04507c29d39ea72f026b7d9fc
Case:                      historical-degraded-sparse
Candidate count:           201
Compact request bytes:     46,022
Compact request ID:        sha256:7ecd536db61a99a33eea0a90cc667935c381d58ff93684bbc953eb0c4b308ce0
Discovery calls:           2
Reproduction calls:        1
Paid calls:                3
Total reported cost:       USD 0.007966518
Semantic repairs:          0
Network retries:           0
```

Secret-free preparation regenerated the same complete request used by Phase 7. Phase 8 removed the preliminary generated route probe and sent the real compact candidate-ID request directly. For every response, the protected runner wrote the HTTP status, allowlisted headers, raw-body hash and protected raw body before parsing or judging metering, identity, content or schema compliance.

## Call 1 — Mercury discovery

```text
Requested model:   inception/mercury-2
Actual model:      inception/mercury-2
Provider:          Inception
Provider slug:     inception
Classification:    invalid-json-content
Input tokens:      19,012
Output tokens:     1,971
Reasoning tokens:  1,957
Finish reason:     length
Reported cost:     USD 0.00616555
```

The retained final content was only the incomplete prefix:

```json
{
  "selected_candidate_ids":
```

Mercury consumed 1,957 of its 1,971 completion tokens as reasoning and exhausted the fixed 2,048-token output allowance before completing the strict JSON envelope.

This is a configuration-specific output-budget result. It proves that the earlier Phase 7 16-token generated route probe was unsuitable for this reasoning model, because even the realistic request with a 2,048-token allowance left only fourteen non-reasoning tokens. It does not establish that Mercury lacks candidate-selection quality or could not complete under a materially different reasoning/output configuration.

Mercury is not admitted to the next comparison from this evidence because the fixed Phase 8 request did not complete. No Mercury rerun or output-budget calibration is authorised under Phase 8.

## Call 2 — GPT-OSS discovery

```text
Requested model:   openai/gpt-oss-120b
Actual model:      openai/gpt-oss-120b
Provider:          DeepInfra
Provider slug:     deepinfra
Classification:    completed
Input tokens:      19,242
Output tokens:     1,109
Reasoning tokens:  628
Finish reason:     stop
Reported cost:     USD 0.000900484
Selected IDs:      7
```

OpenRouter reported seven eligible endpoints and selected DeepInfra on the first attempt. The model returned one complete `selected_candidate_ids` envelope. All seven IDs passed:

```text
candidate identity and duplicate checks
maximum-selection and section/intent limits
repository candidate-selection validation
canonical claim-plan reconstruction
claim-plan semantic validation
deterministic rendering
```

No repair, retry, provider substitution or model fallback occurred.

## Call 3 — pinned GPT-OSS reproduction

The exact real request was repeated with:

```text
provider.only: [deepinfra]
allow_fallbacks: false
```

The actual model and provider remained `openai/gpt-oss-120b` and DeepInfra. The call completed on the first route attempt at the same reported cost and produced the same seven candidate IDs.

Both accepted calls produced identical repository-owned outputs:

```text
Claim-plan SHA-256:        2575f2e6d1ff6c6960f052b5b3f2af783f80fd9f9c7cbd4b6812b889459ebe9b
Rendered Markdown SHA-256: 0f4eb1f0b187db1d4645ac2dc2088de9a993242cdf98bf1ee0c25d8a740c96aa
```

The reproduction demonstrates that the discovered provider identity can be pinned and that the same transport boundary can complete again without provider fallback. Identical outputs are a useful small reproducibility signal, but two calls on one case do not constitute a stability study.

## Harness conclusion

The Phase 7 result should not be interpreted as evidence that low-cost models could not perform the selector task. Phase 7 tested a compound admission boundary that included a 16-token strict-schema generation probe and rejected missing final content before retaining the complete response.

Phase 8 demonstrated the correct order:

```text
real request
  -> retain complete HTTP observation
  -> retain router, reasoning, usage and cost evidence
  -> classify transport and content outcome
  -> validate candidate IDs
  -> reconstruct and render deterministically
```

That design exposed Mercury's actual output-budget failure and allowed GPT-OSS to reach and complete the task. The fundamental problem was therefore partly experimental transport design, not an absence of capable LLMs.

## Evidence and quality distinction

Phase 8 establishes:

- the real 201-candidate request can be transported successfully;
- GPT-OSS 120B can return a valid candidate-ID envelope on that request;
- DeepInfra can be discovered, represented by canonical slug `deepinfra`, pinned and reproduced with fallback disabled;
- complete observable evidence can be retained inside a small cost envelope.

Phase 8 does not establish:

- aggregate precision, recall or F1;
- usefulness across the five frozen Phase 6 cases;
- repeat stability beyond one reproduction;
- incremental value over the deterministic selector;
- acceptable production latency or operational reliability;
- production suitability or publication authority.

No Phase 6 quality conclusion is changed. GPT-OSS is not approved as an active selector merely because its transport works.

## Retained evidence

```text
Prepared artifact: 8844907236
Digest: sha256:14c8560c565c49547e5e32fa88f5d7c9ca32c98d337b3009b7c30c7401ca0f7d

Protected artifact: 8844924119
Digest: sha256:ac3af0e5e825d21cdf62f7266d6db3342514ae35437a4e1015de6d128a1ab295
```

The protected artifact retains all three request bodies, HTTP observations, raw provider responses, router metadata, actual model/provider identity, usage and cost, result classifications, GPT selections, reconstructed claim plans and deterministic renders.

## Operational consequences

- The Phase 8 paid workflow is archived and absent from `main`.
- No Phase 8 rerun is authorised.
- The observable runner, configuration, fake-transport tests and historical evidence references remain retained.
- GPT-OSS/DeepInfra is an eligible candidate for a future governed quality comparison only.
- Mercury receives no quality conclusion and is not carried forward under the current fixed configuration.
- Deterministic selection remains the sole active selector and fallback.
- Automatic generation, scheduling, repository mutation and publication remain disabled.
- Raw provider output remains protected evidence and is not committed or published.

## Future comparison boundary

A future quality comparison may be proposed in a new phase because Phase 8 supplied the previously missing transport evidence. It must not be executed under Phase 8 authority.

At minimum, that phase must define:

- a fixed reviewed corpus, preferably the retained five Phase 6 cases;
- the deterministic comparator and human-reviewed useful candidate sets;
- predeclared precision, recall, F1 and repeat-stability gates;
- exact `openai/gpt-oss-120b` and `deepinfra` identities with fallback disabled;
- the observable HTTP-first evidence boundary retained by Phase 8;
- realistic output and cost ceilings calibrated from 19,242 input, 1,109 output and 628 reasoning tokens per accepted call;
- a fixed repeat count and stopping rule;
- a whole-experiment cost ceiling;
- a separate decision before any production or publication use.

Until that work is separately authorised and produces positive incremental-value evidence, the Phase 6 deterministic selector remains final for active CryptoPulse operation.