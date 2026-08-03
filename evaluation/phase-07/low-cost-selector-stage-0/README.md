# Phase 7 low-cost candidate-selector Stage 0

This directory documents the compatibility and cost screen governed by #314 and #315.
No provider output is committed here.

## Objective

Screen exactly three low-cost OpenRouter model routes against one real-sized candidate-ID
selection request before deciding whether a separately governed five-case comparison is
worth running.

The screen answers only whether each route can preserve exact model/provider identity,
accept strict structured output, provide complete metering, remain inside reviewed cost
ceilings and pass the existing candidate selection boundary once.

It does not establish full-corpus quality, repeat stability, incremental value or
production suitability.

## Fixed models

```text
deepseek/deepseek-v4-flash-0731 -> DeepSeek
openai/gpt-oss-120b             -> DeepInfra
inception/mercury-2             -> Inception
```

The live OpenRouter model and endpoint records remain authoritative at execution time.
No provider substitution, model fallback or alias is permitted.

## Fixed request

Secret-free preparation regenerates `historical-degraded-sparse` through the retained
Phase 6 candidate compiler and deterministic baseline. The provider receives the compact
projection of all 201 candidates, preserving canonical ID order and request identity.

The response remains the existing one-field `selected_candidate_ids` contract. Stage 0
allows no semantic repair.

## Maximum execution

```text
route probes:          3
selector generations:  3
paid calls:             6
semantic repairs:       0
network retries:        0
whole cost:       USD 0.060
```

Every metered response is retained and charged before output or identity validation.
Missing trustworthy cost reserves the reviewed call ceiling.

## Protected outputs

The protected Actions artefact contains current catalogue and route evidence, trusted
SHA, canonical and compact request identities, provider completions, hashes, usage,
latency, cost, validation results, reconstructed plans and rendered-output hashes where
accepted.

Prepared inputs are retained for seven days and protected outputs for thirty days. Raw
provider output is not committed or published.

## Decision boundary

The workflow cannot approve Stage 1, choose a winner, enable a selector, generate a
report, publish the site or write repository state.

After execution:

1. remove the temporary paid workflow through a reviewed cleanup pull request;
2. inspect the protected evidence;
3. commit a separate Stage 0 decision;
4. create a separately budgeted Stage 1 issue only when explicitly authorised.

The deterministic Phase 6 selector remains the sole active selector unless a future
complete comparison provides reviewed positive evidence.
