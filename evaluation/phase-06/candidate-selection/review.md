# Phase 6 bounded candidate-ID selection proof

> **Classification:** repository-owned offline control-flow evidence. No real model or provider call occurred.

- Selection schema: `schemas/crypto-market-candidate-selection-v1.json`
- Selection schema SHA-256: `82e6fe16e8b0ca36e405c525a34209da29f9cccd376dee7e3babe19194dd9694`
- Prompt: `prompts/crypto-market-candidate-selection-v1.txt`
- Cases: `5`
- Scripted scenarios: `25`
- First-pass acceptances: `5`
- Repaired acceptances: `5`
- Deterministic fallbacks: `15`
- Exact fallback matches: `15 / 15`
- Maximum semantic repairs: `1`
- Real provider calls: `0`

## Scenario matrix

| Case | Scenario | Outcome | Attempts | Repairs | Fallback exact |
| --- | --- | --- | ---: | ---: | --- |
| `historical-degraded-sparse` | `accepted_initial` | `accepted_initial` | 1 | 0 | `true` |
| `historical-degraded-sparse` | `accepted_after_repair` | `accepted_after_repair` | 2 | 1 | `true` |
| `historical-degraded-sparse` | `invalid_repair_fallback` | `deterministic_fallback` | 2 | 1 | `true` |
| `historical-degraded-sparse` | `malformed_envelope_fallback` | `deterministic_fallback` | 1 | 0 | `true` |
| `historical-degraded-sparse` | `client_failure_fallback` | `deterministic_fallback` | 1 | 0 | `true` |
| `historical-normal-crosschecked` | `accepted_initial` | `accepted_initial` | 1 | 0 | `true` |
| `historical-normal-crosschecked` | `accepted_after_repair` | `accepted_after_repair` | 2 | 1 | `true` |
| `historical-normal-crosschecked` | `invalid_repair_fallback` | `deterministic_fallback` | 2 | 1 | `true` |
| `historical-normal-crosschecked` | `malformed_envelope_fallback` | `deterministic_fallback` | 1 | 0 | `true` |
| `historical-normal-crosschecked` | `client_failure_fallback` | `deterministic_fallback` | 1 | 0 | `true` |
| `historical-material-move` | `accepted_initial` | `accepted_initial` | 1 | 0 | `true` |
| `historical-material-move` | `accepted_after_repair` | `accepted_after_repair` | 2 | 1 | `true` |
| `historical-material-move` | `invalid_repair_fallback` | `deterministic_fallback` | 2 | 1 | `true` |
| `historical-material-move` | `malformed_envelope_fallback` | `deterministic_fallback` | 1 | 0 | `true` |
| `historical-material-move` | `client_failure_fallback` | `deterministic_fallback` | 1 | 0 | `true` |
| `adversarial-prompt-injection` | `accepted_initial` | `accepted_initial` | 1 | 0 | `true` |
| `adversarial-prompt-injection` | `accepted_after_repair` | `accepted_after_repair` | 2 | 1 | `true` |
| `adversarial-prompt-injection` | `invalid_repair_fallback` | `deterministic_fallback` | 2 | 1 | `true` |
| `adversarial-prompt-injection` | `malformed_envelope_fallback` | `deterministic_fallback` | 1 | 0 | `true` |
| `adversarial-prompt-injection` | `client_failure_fallback` | `deterministic_fallback` | 1 | 0 | `true` |
| `adversarial-source-disagreement` | `accepted_initial` | `accepted_initial` | 1 | 0 | `true` |
| `adversarial-source-disagreement` | `accepted_after_repair` | `accepted_after_repair` | 2 | 1 | `true` |
| `adversarial-source-disagreement` | `invalid_repair_fallback` | `deterministic_fallback` | 2 | 1 | `true` |
| `adversarial-source-disagreement` | `malformed_envelope_fallback` | `deterministic_fallback` | 1 | 0 | `true` |
| `adversarial-source-disagreement` | `client_failure_fallback` | `deterministic_fallback` | 1 | 0 | `true` |

## Validation matrix

| Invalid selection | Stable diagnostics |
| --- | --- |
| `unknown` | `unknown_selected_candidate_id` |
| `duplicate` | `duplicate_selection` |
| `excessive` | `excessive_selection` |
| `redundancy` | `selection_redundancy_violation` |
| `mixed_bundle` | `selected_candidate_bundle_mismatch` |

## Proven boundaries

- The canonical response object contains only `selected_candidate_ids`.
- Model list order is ignored; accepted IDs are restored to canonical candidate order.
- Only a structurally complete ID array is eligible for one semantic repair.
- Malformed envelopes and client/provider-class failures fall back immediately.
- A second invalid response falls back without a third attempt.
- Fallback uses the exact Slice 4 selected IDs, claim plan and Markdown.
- Candidate and evidence permutations preserve request and final-output bytes.
- No model-quality, cost or latency comparison is made in Slice 5.
