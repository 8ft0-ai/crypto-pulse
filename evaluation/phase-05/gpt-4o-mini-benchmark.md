# GPT-4o mini paid benchmark

Issue: #205  
Protected run contract: #206  
Planning decision: #199

This benchmark tests one explicit paid OpenRouter configuration after the bounded free-model path produced no routable governed output.

## Model and current catalogue evidence

Catalogue checked: 11 July 2026

```text
Model:                       openai/gpt-4o-mini
Context:                     128,000 tokens
Maximum completion:          16,384 tokens
Prompt price:                USD 0.15 / million tokens
Completion price:            USD 0.60 / million tokens
Required parameters:         response_format, structured_outputs
Known expiry:                none listed
```

Catalogue eligibility does not establish a usable Zero Data Retention route. The protected route probe must prove that separately.

## Approved benchmark boundary

```text
Route preflight:               1 logical call
Contract smoke test:           1 logical call
Full corpus:                   5 cases × 2 repeats
Maximum logical calls:         12
Maximum attempts per call:     3
Minimum interval:              10 seconds
Per-generation cost ceiling:   USD 0.01
Whole benchmark ceiling:       USD 0.15
```

At the published catalogue price, a representative request with 5,000 input tokens and 1,000 output tokens costs approximately USD 0.00135. The higher source-controlled ceilings allow for the actual evidence bundle, 4,000-token output bound and retry uncertainty while preventing an open-ended paid run.

## Governance boundary

```text
ZDR:                           required
Data collection:               deny
Required parameters:           enforced
Same-model provider fallback:  allowed and evidenced
Cross-model fallback:          disabled
Automatic generation:          disabled
Publication writes:            none
Evaluation output reused:      no
```

The benchmark qualifies only with a real ZDR route, a passing smoke test, ten out of ten hard-governance corpus passes, complete cost metadata and total cost within the approved ceiling. A separate reviewer decision PR is required before #189 can resume.
