# Governed semantic claim-plan model calibration

Status: superseded historical calibration. The manual workflow entry point has been removed from the GitHub Actions UI. The runner, configuration, documentation, Git history and protected run artefacts remain available for audit.

Issue #267 added this bounded calibration after protected model-selection run `29231039012` exposed route and budget incompatibilities that prevented a fair model comparison.

## Historical purpose

The calibration answered one narrow question per shortlisted model: could the then-current OpenRouter route complete the real CryptoPulse semantic claim-plan contract on the frozen `historical-normal-crosschecked` case?

It did not rank models or select a production winner.

## Historical call and cost boundary

```text
GPT-5.6 Sol:  one route probe + one full-contract call
Nex N2 Mini: one route probe + one full-contract call
MiniMax M3:  one route probe + one full-contract call
substantive generations: exactly 3
whole-run ceiling: USD 0.50
```

GPT-5.6 used a USD 0.15 full-call ceiling so valid responses were not censored by the earlier USD 0.10 gate. MiniMax M3 received an 8,000-token completion allowance for this compatibility check. The prompt, provider-projected schema, evidence, validator and renderer remained unchanged.

## What it discovered

Protected run [`29235513924`](https://github.com/8ft0-ai/crypto-pulse/actions/runs/29235513924) showed that:

- GPT-5.6 could complete the contract but cross-source USD spot evidence lacked a canonical shared measure;
- Nex required a user-role message in addition to the governed system message;
- MiniMax completed after its output allowance was raised but failed the semantic intent taxonomy;
- validator-rejected plans still needed to be excluded from soft quality scoring.

The complete discovery history and self-reflection are recorded in [`../evaluation/phase-05/semantic-model-evaluation-retrospective.md`](../evaluation/phase-05/semantic-model-evaluation-retrospective.md).

## Diagnostics

The historical runner emitted progress lines before and after each route probe and full-contract call. It retained redacted provider error metadata and usage observations without storing authorization data or model reasoning.

## Superseding workflow

Do not rerun this three-model calibration. MiniMax M3 does not advance, and the contract corrections are implemented only in the active two-model workflow.

Use **Semantic plan calibration — GPT-5.6 + Nex only** from `main`.
