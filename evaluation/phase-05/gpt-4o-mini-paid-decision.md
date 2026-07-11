# GPT-4o mini paid benchmark decision

Decision: **paid-proof-no-go**  
Selected configuration: **none**

Protected run [`29146222273`](https://github.com/8ft0-ai/crypto-pulse/actions/runs/29146222273) completed successfully as evaluation infrastructure against trusted `main` commit `475b56d5b547d30439428379585005d621632255`. The exact `openai/gpt-4o-mini` configuration passed live catalogue, pricing, structured-output and account-quota screening, but its first strict request returned HTTP `404`, classified as `ineligible_routing`.

No endpoint was available under the required provider policy:

```text
ZDR:                         required
data collection:             deny
required parameters:         enforced
same-model provider fallback: allowed
cross-model fallback:        disabled
```

This is a routing and governance result, not a model-quality score. GPT-4o mini produced no completion, so readability, usefulness, grounding, semantic-policy compliance, reproducibility, latency and token usage are unavailable.

## Reviewed evidence

```text
Implementation issue / PR:    #205 / #208
Execution issue:              #206
Workflow run:                 29146222273
Comparison job:               86528132043
Trusted main SHA:             475b56d5b547d30439428379585005d621632255
Artifact ID:                  8246809348
Artifact digest:              sha256:2ecd45dbe33e21132f3594817f66a1781b6c1ebb2c9b6818a893948a6f3916f1
Artifact expiry:              10 August 2026
```

## Catalogue and quota gates

At execution time OpenRouter listed `openai/gpt-4o-mini` as available and eligible, with both `response_format` and `structured_outputs` advertised.

```text
Prompt price:                 USD 0.15 / million tokens
Completion price:             USD 0.60 / million tokens
Approved per-generation cap:  USD 0.01
Approved benchmark cap:       USD 0.15
Account remaining:            USD 9.9860193
Quota assessment:             appears sufficient
```

The failure was not caused by insufficient account credit, catalogue disappearance, price drift or missing structured-output support.

## Funnel result

```text
Maximum logical calls:        12
Completed logical calls:       1
HTTP attempts:                 1
Route-preflight passes:        0
Smoke tests run:               0
Full-corpus runs:              0 / 10
Accepted outputs:              0
Recorded cost:                 USD 0
```

The evaluator stopped correctly after the non-retryable route failure. It did not spend the remaining eleven logical calls.

## Interpretation

The evidence supports this precise conclusion:

> The paid `openai/gpt-4o-mini` OpenRouter configuration is not routable under CryptoPulse's required ZDR and data-collection policy at the reviewed execution time.

It does **not** establish that GPT-4o mini produces poor market analysis, because no output was generated. It also does not justify weakening ZDR merely to obtain a route.

## Planning effect

After this decision merges:

- #206 is complete with outcome `paid-proof-no-go`;
- #189 remains blocked because no approved model configuration has produced an accepted governed run;
- the exact OpenRouter GPT-4o mini path is closed for Phase 5;
- no automatic or rolling LLM report generation is enabled;
- the recommended default for #199 is `park-and-close` unless a separately approved direct-provider or revised-policy investigation has clear product and governance justification.

No raw completion, credential, generated site output or evaluation result used as market evidence is committed by this decision.
