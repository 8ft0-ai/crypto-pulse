# Five-model catalogue screen outcome

Date: 13 July 2026.

Source workflow: [`29246391801`](https://github.com/8ft0-ai/crypto-pulse/actions/runs/29246391801).

Trusted `main` SHA: `5bb4c8a8c9816353fee6487eb39f7906333ffada`.

Plan: `semantic-plan-model-catalogue-screen/v1`.

Observed cost: USD 0.0200591105 against a USD 0.15 ceiling.

## Outcome

The protected workflow completed successfully, retained the correct artefacts and attempted three of the five possible full-contract calls. No model passed the complete screen, but the result is not a five-model semantic no-go. The candidates reached materially different boundaries.

| Model | Route | Full contract | Reviewed interpretation |
| --- | --- | --- | --- |
| DeepSeek V4 Flash | Failed after an HTTP 200 provider response | Not attempted | The route probe allowed only 16 output tokens while `high` reasoning was enabled. It exhausted the allowance before visible content remained. Route and semantic compatibility remain unresolved. |
| GPT-5.6 Luna | Passed through OpenAI | Validator rejected | The completed compact plan mixed multiple source subjects in one `source_status` claim. The validator rule was not explicit in prompt v1, so this is contract-discovery evidence rather than a fair model no-go. |
| Qwen3.6 Flash | Passed through Alibaba | Truncated | The full request exhausted its 4,000-token allowance with `finish_reason: length`. Semantic compatibility remains unresolved. |
| MiMo V2.5 Pro | No eligible route | Not attempted | OpenRouter reported that no endpoint could handle the complete governed request and provider policy. The model does not advance under the current policy. |
| Seed 2.0 Mini | Passed through Seed | Validator rejected | The completed plan produced multiple source-status, snapshot-status and data-quality taxonomy errors and selected too many claims. This was a fair semantic failure for the reviewed configuration. |

All rejected or missing plans were correctly unscored. No quality leaderboard or deployment selection was produced.

## Contract finding

The canonical validator requires a `source_status` claim to describe one source subject only. Prompt v1 said that `source_status` must use source-status evidence, but it did not expose the one-subject grouping rule.

The correction is a new immutable prompt artefact, `crypto-market-claim-plan/v2`, which preserves the v1 contract and adds:

> A `source_status` claim must describe exactly one source subject. Every cited evidence record in that claim must belong to that same source subject. Use separate claims for separate sources.

The historical v1 prompt remains unchanged.

## Advancement boundary

Issue #275 prepares one corrective screen for:

```text
openai/gpt-5.6-luna
deepseek/deepseek-v4-flash
qwen/qwen3.6-flash
```

The corrected screen uses prompt v2, a representative DeepSeek route allowance and an 8,000-token Qwen full-contract allowance. It remains a compatibility screen rather than a ranking or selection exercise.

MiMo V2.5 Pro and Seed 2.0 Mini do not advance in that screen. A future reconsideration would require a separately reviewed provider-policy or model-configuration change.
