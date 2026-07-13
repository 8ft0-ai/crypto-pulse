# Final semantic claim-plan model calibration

Issue #269 adds one final compatibility calibration after run `29235513924` identified two correctable integration boundaries. GPT-5.6 completed the real contract but cross-source spot prices used inconsistent field names. Nex N2 Mini required a user-role message in addition to the governed system prompt. MiniMax M3 does not advance because its completed plan failed the semantic intent taxonomy.

The discovery history and lessons that led to this final calibration are recorded in [`../evaluation/phase-05/semantic-model-evaluation-retrospective.md`](../evaluation/phase-05/semantic-model-evaluation-retrospective.md).

## Scope

The final run contains exactly two substantive generations:

```text
GPT-5.6 Sol:  one route probe + one full-contract call
Nex N2 Mini: one route probe + one full-contract call
whole-run ceiling: USD 0.25
```

GPT-5.6 retains its USD 0.15 per-call ceiling. Nex retains a USD 0.02 per-call ceiling. The combined model ceilings are USD 0.21, leaving USD 0.04 beneath the hard whole-run boundary.

## Evidence normalisation

Before either call, the frozen smoke-case bundle is copied into a derived protected directory. Coinbase Exchange USD spot records whose source field is `price` are mapped to the canonical measure `price_usd`. Source identity, source path, subject, observed time, value and unit are unchanged. The derived bundle receives a recomputed content-addressed bundle ID, and the exact transformation is retained in `evidence-normalisation.json`.

## Nex request compatibility

The governed system message remains unchanged. For Nex N2 Mini only, the transport adds one minimal user-role execution message when the request otherwise contains no user message. Existing user messages are never duplicated.

## Scoring boundary

Semantic coverage, materiality, restraint and repeat stability are available only after the canonical validator accepts the plan. Missing or rejected plans are reported as unscored with null quality metrics. Empty failures cannot earn stability points.

## Preflight visibility

Before the protected paid job begins, the preparation job writes the exact plan identity, trusted SHA, candidates, smoke case, substantive-call count, cost ceiling, evidence transform, Nex compatibility message, validator-gated scoring state and MiniMax exclusion to the GitHub Actions summary.

This preflight is part of the experiment contract. A reviewer should confirm it before interpreting any result.

## Trust boundary

The workflow is manual, trusted-main, read-only, protected-environment and artefact-only. It cannot publish analysis or update repository state.

Dispatch **Semantic plan calibration — GPT-5.6 + Nex only** once from `main`. No similarly named three-model calibration workflow should remain available in the Actions UI.

## Cleanup validation

Issue #271 and PR #272 removed the obsolete manual workflow entry point and added the retrospective and preflight protections. PR validation runs `29244079165` and `29244135867` passed semantic integration, public-data policy compatibility, the full unit suite, documentation validation, generated-output protection, static-site build and artefact verification. No paid model calls were made by that PR.
