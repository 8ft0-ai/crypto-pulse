# Phase 5 final bounded free-model decision

## Decision

**Outcome: `free-proof-no-go`**

No candidate from the final bounded free-model experiment qualified for the governed Phase 5 proof path. The free-model option is closed for this phase. No additional free candidates should be tested under #201 or Phase 5.

This decision does not select a paid model, weaken Zero Data Retention, enable cross-model fallback, or authorise automatic or rolling report generation. The remaining planning decision in #199 is explicitly limited to:

1. approve a separately scoped paid, ZDR-compatible proof; or
2. park the LLM path and close Phase 5 with an operational no-go.

Issue #189 remains blocked until one of those directions is explicitly approved.

## Reviewed protected run

```text
Workflow:             Governed LLM model evaluation
Run:                  29144514292
Comparison job:       86523647793
Trusted main SHA:     bf25c6c4ff2924f18bd28050d5b6016676045192
Candidate config PR:  #203
Evaluator PR:         #202
```

The comparison workflow completed successfully as infrastructure. The trusted-main guard, immutable corpus preparation, protected evaluation, summary generation and artefact upload all passed.

Reviewed artefact:

```text
Name:       governed-llm-evaluation-29144514292-1
Artifact:   8246302011
Digest:     sha256:a51f829291bf823c7c4d7b5c626b24cacd856986c9841db07552811a8fc066a8
Retained:   until 2026-08-10T07:28:55Z
```

The machine-readable decision record contains hashes for every reviewed summary, attempt, availability, quota and reviewer file.

## Funnel result

```text
Maximum logical calls:       26
Completed logical calls:      3
HTTP attempts:                5
Route-preflight candidates:   3
Route-preflight passes:       0
Contract smoke-test passes:   0
Full-corpus finalists:        0
Accepted model outputs:       0
Estimated cost:               USD 0
```

The staged evaluator therefore avoided up to 23 unnecessary later calls. No candidate that failed route preflight consumed a smoke-test or corpus request.

## Candidate results

### `nvidia/nemotron-nano-9b-v2:free`

The model remained listed, unexpired, zero-priced and structured-output eligible at execution time. Its one real route-preflight request returned HTTP `404` and was classified `ineligible_routing`.

No endpoint for the exact model satisfied the required ZDR and provider-policy constraints. This was non-retryable by design. The model did not enter smoke testing or the full corpus.

### `openai/gpt-oss-20b:free`

The model remained listed, unexpired, zero-priced and structured-output eligible at execution time. Its route-preflight request was sent after an 11.456758-second pacing delay and returned HTTP `404`, classified `ineligible_routing`.

No endpoint for the exact model satisfied the required ZDR and provider-policy constraints. The model did not enter smoke testing or the full corpus.

### `cognitivecomputations/dolphin-mistral-24b-venice-edition:free`

The model remained listed, zero-priced and structured-output eligible, with a catalogue expiry of 19 July 2026. Its route preflight returned HTTP `429` on all three bounded attempts:

```text
Attempt 1: 10.604907s minimum-interval + jitter delay → 429
Attempt 2: 22.225381s Retry-After + jitter delay       → 429
Attempt 3: 31.077794s Retry-After + jitter delay       → 429
```

The retry budget was exhausted. Under #201, exhausting the bounded retry policy is disqualifying. The model did not enter smoke testing or the full corpus.

## Quota interpretation

The authenticated key-status endpoint reported:

```text
is_free_tier:               false
monetary limit:             10
monetary usage:             0.0139807
monetary limit remaining:   9.9860193
request budget assessment:  appears_sufficient
rate-limit headroom known:  false
```

This established that the monetary limit was not exhausted. It did not prove model-route rate-limit headroom, which the Venice route subsequently demonstrated was unavailable within the bounded retry window.

The result must not be interpreted as a general account-credit failure. It is evidence about the exact selected free routes under the approved provider policy at the recorded execution time.

## What the run did and did not prove

The run conclusively established that none of the three selected free configurations could proceed through the governed funnel:

- two exact models had no ZDR-compatible route;
- one exact model remained rate-limited after correct pacing and bounded retries;
- no candidate reached the contract smoke test;
- no candidate reached the full corpus.

It did **not** produce evidence about generated-analysis quality. There were no provider completions to assess for schema validity, evidence grounding, semantic policy, usefulness, readability, latency, token usage or reproducibility. Those dimensions remain `unavailable`, not zero-scored.

## Governance boundaries retained

```text
ZDR:                              required
Data collection:                  denied
Required parameters:              enforced
Same-model provider fallback:     allowed
Cross-model fallback:             disabled
Paid model approval:              none
Automatic generation:             disabled
Rolling report generation:        disabled
Evaluation output used as evidence: no
Raw provider output committed:    no
Secrets committed:                no
Generated _site committed:        no
```

## Planning effect

On merge of this decision:

- #201 is complete with `free-proof-no-go`;
- the free-model option in #199 is closed;
- further free-model testing is out of scope for Phase 5;
- #189 remains blocked;
- #181 remains open only long enough to record the explicit `paid-proof` or `park-and-close` planning decision.

The historical no-go in PR #198 remains unchanged and valid for its earlier two-model experiment. This record adds a separate result for the final paced viability experiment rather than rewriting prior evidence.
