# Governed semantic claim-plan model selection

Issue #263 adds a new model-selection slice after the completed GPT-4o mini semantic-plan no-go. It does not alter that decision or the earlier Phase 5 model-evaluation history.

## Evaluation boundary

The run uses the checked-in semantic claim-plan prompt, canonical schema, strict-schema projection, frozen public-data corpus, fail-closed validator and deterministic renderer. Raw completions and generated analysis remain protected workflow artefacts.

The manual workflow checks out trusted `main`, freezes the corpus in a secret-free job, then executes the exact trusted SHA in the protected `governed-llm-dry-run` environment. Repository permissions are read-only and checkout credentials are not persisted.

## Bounded Stage 1 plan

```text
GPT-5.6 Sol:  five cases × two repeats
Nex N2 Mini: five cases × four repeats
MiniMax M3:  five cases × four repeats
maximum substantive generations: 50
maximum whole-run cost: USD 2.50
```

Each model receives a separate route probe and separate price, per-call and aggregate cost ceilings. Cross-model fallback, automatic generation and publication remain disabled.

GPT-5.6 Sol is benchmark-only. The production decision is whether Nex N2 Mini or MiniMax M3 retains sufficient benchmark quality while clearing every hard governance gate.

## Provider compatibility

The runner sends the same semantic contract to every candidate. It may omit a request parameter only when the checked model configuration explicitly records that the current route does not support it. GPT-5.6 Sol therefore omits `temperature`; the prompt, evidence, schema, output-token limit, provider policy, validator and renderer remain unchanged.

## Review outputs

The artefact bundle contains live catalogue evidence, excluded-model evidence, route-preflight results, raw completions, canonical claim plans, validator reports, deterministic rendered outputs, provenance, attempts, per-case expectation results, a reviewer CSV and separate quality and deployment leaderboards.

No winner is promoted automatically. Stage 1 must be reviewed before at most two affordable finalists move to a broader hidden corpus.
