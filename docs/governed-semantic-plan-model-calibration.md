# Governed semantic claim-plan model calibration

Issue #267 adds a bounded calibration step after protected model-selection run `29231039012` exposed route and budget incompatibilities that prevented a fair model comparison.

## Purpose

Calibration answers one narrow question per shortlisted model: can the current OpenRouter route complete the real CryptoPulse semantic claim-plan contract on the frozen `historical-normal-crosschecked` case?

It does not rank models or select a production winner.

## Call and cost boundary

```text
GPT-5.6 Sol:  one route probe + one full-contract call
Nex N2 Mini: one route probe + one full-contract call
MiniMax M3:  one route probe + one full-contract call
substantive generations: exactly 3
whole-run ceiling: USD 0.50
```

GPT-5.6 uses a USD 0.15 full-call ceiling so valid responses are not censored by the earlier USD 0.10 gate. MiniMax M3 receives an 8,000-token completion allowance for this compatibility check. The prompt, provider-projected schema, evidence, validator and renderer remain unchanged.

## Diagnostics

The runner emits progress lines before and after each route probe and full-contract call. It retains redacted provider error metadata and usage observations without storing authorization data or model reasoning. A failed call without a canonical plan is reported as unscored; it receives no quality or stability value.

## Trust boundary

The workflow is manual, read-only and artefact-only. It freezes the existing semantic corpus without secrets, then checks out and executes the exact trusted `main` SHA in the protected `governed-llm-dry-run` environment. It cannot publish analysis or update repository state.

After review and merge, dispatch **Governed semantic plan model calibration** once from `main`. A broader evaluation should proceed only for routes that pass this full-contract calibration.
