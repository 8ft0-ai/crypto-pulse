# Corrective semantic claim-plan screen

Issue #275 adds a bounded corrective compatibility screen after protected run `29246391801` identified three unresolved model configurations and one hidden prompt/validator rule.

## Purpose

The screen tests exactly:

```text
openai/gpt-5.6-luna
deepseek/deepseek-v4-flash
qwen/qwen3.6-flash
```

It asks whether each corrected configuration can route, complete and produce one validator-accepted claim plan over the same normalised `historical-normal-crosschecked` evidence bundle.

It is not a benchmark, leaderboard or deployment decision.

## Prompt v2

The historical `crypto-market-claim-plan/v1` prompt remains unchanged. The screen uses the separate immutable artefact `prompts/crypto-market-claim-plan-v2.md` with version `crypto-market-claim-plan/v2`.

Prompt v2 preserves every v1 rule and adds the canonical validator's source grouping rule:

> A `source_status` claim must describe exactly one source subject. Every cited evidence record in that claim must belong to that same source subject. Use separate claims for separate sources.

The prompt path and version are retained in runtime and summary artefacts.

## Corrective request envelopes

| Model | Route probe allowance | Full-contract allowance | Reasoning policy |
| --- | ---: | ---: | --- |
| GPT-5.6 Luna | 64 tokens | 4,000 tokens | `none`; temperature omitted |
| DeepSeek V4 Flash | 256 tokens | 12,000 tokens | `high`; reasoning content excluded |
| Qwen3.6 Flash | 64 tokens | 8,000 tokens | explicitly disabled |

The DeepSeek route probe is deliberately larger than the historical 16-token probe. Qwen receives a complete 8,000-token opportunity after its earlier 4,000-token truncation.

## Cost boundary

```text
Luna model ceiling:      USD 0.050
DeepSeek model ceiling:  USD 0.015
Qwen model ceiling:      USD 0.020
Combined model ceilings: USD 0.085
Whole-run ceiling:       USD 0.10
```

The runner fails closed on live price increases, missing structured-output support, incompatible reasoning metadata, route incompatibility, missing cost evidence or any ceiling breach.

## Exclusions

MiMo V2.5 Pro and Seed 2.0 Mini are not retried:

- MiMo had no route eligible for the complete governed request and provider policy.
- Seed completed fairly but failed multiple semantic taxonomy rules and selected too many claims.

Those reasons are retained in the checked-in plan and protected artefact.

## Shared controls

The screen reuses:

- exact requested model identity;
- `require_parameters: true` and `data_collection: deny`;
- disabled cross-model fallback;
- canonical Coinbase USD `price` to `price_usd` evidence normalisation;
- strict claim-plan schema;
- canonical semantic validator;
- deterministic renderer;
- redacted provider diagnostics;
- validator-gated expectation scoring;
- unscored rejected or missing plans.

## Trust boundary

The workflow is manual, trusted-main, read-only, protected-environment and artefact-only. It cannot publish analysis, modify repository content, select a production model or enable automatic generation.

After merge, dispatch **Semantic plan correction — Luna + DeepSeek + Qwen** once from `main` and verify the preflight before approving the protected job.
