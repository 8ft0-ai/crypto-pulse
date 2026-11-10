# Final bounded free-model candidates

Issue: #201  
Parent planning decision: #199  
Evaluator implementation: #200 / PR #202  
Experiment configuration: `config/llm-evaluation-free-proof.yml`  
Historical evaluation configuration: `config/llm-evaluation.yml` — unchanged  
Catalogue endpoint: `https://openrouter.ai/api/v1/models`  
Catalogue checked at: `2026-07-11T07:14:28Z`

This record selects the exact candidates for the final bounded free-model viability experiment. It is a catalogue-screening record only. It does not claim that any candidate has a Zero Data Retention-compatible route, can satisfy the governed analysis contract, or is approved for the Phase 5 production-proof path.

The final experiment uses a dedicated configuration so that the original #188 evaluation plan and the no-go evidence recorded by PR #198 remain immutable and reproducible.

## Selection constraints

Each selected candidate was present in the OpenRouter catalogue at the recorded check time and met the repository's preflight screening rules:

- explicit `provider/model:free` slug;
- prompt price `0`;
- completion price `0`;
- both `response_format` and `structured_outputs` advertised;
- context capacity sufficient for the current bounded evidence bundle and 4,000-token output limit;
- not expired on 11 July 2026;
- not a router, latest-model alias or paid variant.

Actual ZDR routing, data-collection denial, requested/actual model identity and provider behaviour must be established by the protected route-preflight stage after this configuration merges.

## Selected candidates

### `nvidia/nemotron-nano-9b-v2:free`

```text
Evaluation key:       nemotron-nano-9b-v2
Role in config:       current_candidate (evaluation anchor only)
Prompt price:         0
Completion price:     0
Context length:       128,000
Advertised parameters: response_format, structured_outputs
Known expiry:         none listed
```

Rationale: keeps an NVIDIA Nemotron lineage in the comparison while replacing the previously rejected Super route with a materially different explicit free model. The absence of a listed expiry makes it useful for testing whether a longer-lived free listing is operationally more stable. This role does not retain or reinstate the historical pinned model.

### `openai/gpt-oss-20b:free`

```text
Evaluation key:       gpt-oss-20b
Role in config:       eligible_alternative
Prompt price:         0
Completion price:     0
Context length:       131,072
Maximum completion:   32,768
Advertised parameters: response_format, structured_outputs
Known expiry:         none listed
```

Rationale: a distinct open-weight model/provider family with sufficient context and output capacity, explicit structured-output support and no listed expiry. It provides a useful contrast to the Nemotron candidate without introducing a paid dependency.

### `cognitivecomputations/dolphin-mistral-24b-venice-edition:free`

```text
Evaluation key:       venice-dolphin-mistral-24b
Role in config:       eligible_alternative
Prompt price:         0
Completion price:     0
Context length:       32,768
Advertised parameters: response_format, structured_outputs
Known expiry:         2026-07-19
```

Rationale: the earliest-expiring eligible candidate. Including it exercises the deterministic finalist rule's expiry-risk ordering and tests a separate Mistral-derived model/provider route. Its 32,768-token context remains above the current bounded request and 4,000-token output requirement, but the protected smoke test must prove the real request fits and validates.

## Excluded previous candidates

### `qwen/qwen3-next-80b-a3b-instruct:free`

Excluded because the current catalogue no longer reports zero prompt and completion prices. At the recorded check it advertised:

```text
Prompt price:       0.00000009
Completion price:   0.0000011
```

The `:free` suffix alone is not sufficient; repository eligibility requires both catalogue prices to be exactly zero at execution time. The model may also be rejected again by the workflow if the catalogue changes between this review and dispatch.

### `nvidia/nemotron-3-super-120b-a12b:free`

Excluded from the final candidate set because protected run `29142348720` already established that no endpoint for this exact model met the required ZDR policy. Repeating it with pacing would not address that structural routing result.

## Experiment boundary

After this configuration merges, the protected workflow will:

1. query authenticated key/quota status;
2. check the catalogue again at execution time;
3. perform one minimal ZDR route preflight per eligible candidate;
4. run the locked normal contract smoke test only for route-pass candidates;
5. advance at most two candidates to the five-case, two-repeat corpus;
6. retain all raw responses and attempt records as non-published workflow artefacts;
7. produce only a decision candidate for later reviewer approval.

The configuration does not change:

```text
ZDR:                         required
data_collection:             deny
require_parameters:          true
same-model provider fallback: allowed
cross-model fallback:        disabled
paid calls:                  prohibited
automatic generation:        disabled
report/publication writes:   none
```

The historical no-go recorded by PR #198 remains accurate for the earlier configurations and execution policy.
