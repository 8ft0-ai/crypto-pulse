# Five-model semantic claim-plan catalogue screen

Status: completed historical compatibility screen. The manual workflow entry point has been removed from the GitHub Actions UI. The runner, configuration, documentation, Git history and protected artefact remain available for audit.

Issue #273 introduced a catalogue-expansion screen for:

```text
deepseek/deepseek-v4-flash
openai/gpt-5.6-luna
qwen/qwen3.6-flash
xiaomi/mimo-v2.5-pro
bytedance-seed/seed-2.0-mini
```

Protected run [`29246391801`](https://github.com/8ft0-ai/crypto-pulse/actions/runs/29246391801) completed against trusted `main` SHA `5bb4c8a8c9816353fee6487eb39f7906333ffada`. It spent USD 0.0200591105 beneath a USD 0.15 ceiling and produced no model selection or leaderboard.

The reviewed result is recorded in [`../evaluation/phase-05/catalogue-screen-29246391801.md`](../evaluation/phase-05/catalogue-screen-29246391801.md).

## What the screen established

- GPT-5.6 Luna completed a compact plan but exposed a prompt/validator mismatch around grouping multiple source subjects in one `source_status` claim.
- DeepSeek V4 Flash reached a provider route, but the 16-token route probe was not representative for enabled high reasoning.
- Qwen3.6 Flash passed routing but exhausted its 4,000-token full-contract allowance.
- MiMo V2.5 Pro had no endpoint eligible for the complete governed request and provider policy.
- Seed 2.0 Mini completed fairly but failed multiple semantic taxonomy rules.

Rejected and missing plans were correctly unscored. No failed model received quality or stability credit.

## Superseding screen

Do not rerun the five-model workflow.

Issue #275 adds prompt `crypto-market-claim-plan/v2` and a corrective workflow named **Semantic plan correction — Luna + DeepSeek + Qwen**. It advances only the three unresolved candidates with the specific contract and output-envelope corrections identified by the historical screen.

MiMo and Seed remain excluded for their reviewed reasons. The still-pending Sol/Nex calibration also moves to prompt v2 before it is treated as fair evidence.
