# Final semantic claim-plan model calibration

Issue #269 adds one final compatibility calibration for GPT-5.6 Sol and Nex N2 Mini. Run `29235513924` identified two integration corrections: canonical cross-source price normalisation and a required user-role execution message for Nex. MiniMax M3 does not advance because its completed plan failed the semantic intent taxonomy.

The later five-model screen `29246391801` exposed one additional contract defect: the canonical validator requires one source subject per `source_status` claim, but prompt v1 did not state that rule. The final calibration therefore now uses prompt `crypto-market-claim-plan/v2` before either result is treated as fair evidence.

The discovery history is recorded in [`../evaluation/phase-05/semantic-model-evaluation-retrospective.md`](../evaluation/phase-05/semantic-model-evaluation-retrospective.md), and the prompt-v2 finding is recorded in [`../evaluation/phase-05/catalogue-screen-29246391801.md`](../evaluation/phase-05/catalogue-screen-29246391801.md).

## Scope

The final run contains exactly two route probes and two substantive generations:

```text
GPT-5.6 Sol:  one route probe + one full-contract call
Nex N2 Mini: one route probe + one full-contract call
whole-run ceiling: USD 0.25
```

GPT-5.6 retains its USD 0.15 per-generation ceiling and USD 0.18 model ceiling. Nex retains a USD 0.02 per-generation ceiling and USD 0.03 model ceiling. The combined model ceilings are USD 0.21, leaving USD 0.04 beneath the hard whole-run boundary.

## Prompt v2

The historical `prompts/crypto-market-claim-plan-v1.md` remains unchanged. The workflow uses the separate immutable `prompts/crypto-market-claim-plan-v2.md` artefact and records version `crypto-market-claim-plan/v2`.

Prompt v2 preserves every v1 rule and adds:

> A `source_status` claim must describe exactly one source subject. Every cited evidence record in that claim must belong to that same source subject. Use separate claims for separate sources.

The prompt path and version are retained in runtime and summary artefacts.

## Evidence normalisation

Before either call, the frozen smoke-case bundle is copied into a derived protected directory. Coinbase Exchange USD spot records whose source field is `price` are mapped to the canonical measure `price_usd`. Source identity, source path, subject, observed time, value and unit are unchanged. The derived bundle receives a recomputed content-addressed bundle ID, and the exact transformation is retained in `evidence-normalisation.json`.

## Nex request compatibility

For Nex N2 Mini only, the transport adds one fixed user-role execution message when the request otherwise contains no user message. Existing user messages are never duplicated. GPT-5.6 preserves the existing message shape and omits unsupported temperature.

## Scoring boundary

Semantic coverage, materiality and restraint are available only after the canonical validator accepts the plan. Missing or rejected plans are reported as unscored with null quality metrics. No single-call leaderboard or deployment selection is produced.

## Preflight visibility

Before the protected paid job begins, the preparation job writes the exact plan identity, prompt version, trusted SHA, candidates, case, route and generation counts, cost ceiling, evidence transform, Nex compatibility message, validator-gated scoring state and MiniMax exclusion to the GitHub Actions summary.

This preflight is part of the experiment contract. A reviewer should confirm it before interpreting any result.

## Trust boundary

The workflow is manual, trusted-main, read-only, protected-environment and artefact-only. It cannot publish analysis or update repository state.

Dispatch **Semantic plan calibration — GPT-5.6 + Nex only** once from `main` only after this prompt-v2 change is merged. The expected plan identity is `semantic-plan-model-final-calibration/v2`.
