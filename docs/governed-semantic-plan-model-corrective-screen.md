# Corrective semantic claim-plan screen

Status: **completed historical experiment; not dispatchable**.

Issue #275 added a bounded corrective compatibility screen after protected run `29246391801` identified three unresolved model configurations and one hidden prompt/validator rule.

The corrective screen ran as workflow run [`29285569716`](https://github.com/8ft0-ai/crypto-pulse/actions/runs/29285569716). All three route probes and all three full-contract calls completed, but no model produced a validator-accepted full claim plan.

The reviewed result is recorded in [`../evaluation/phase-05/corrective-screen-29285569716.md`](../evaluation/phase-05/corrective-screen-29285569716.md).

## Historical purpose

The screen tested exactly:

```text
openai/gpt-5.6-luna
deepseek/deepseek-v4-flash
qwen/qwen3.6-flash
```

It asked whether each corrected configuration could route, complete and produce one validator-accepted claim plan over the same normalised `historical-normal-crosschecked` evidence bundle.

It was not a benchmark, leaderboard or deployment decision.

## Prompt v2

The historical `crypto-market-claim-plan/v1` prompt remains unchanged. The screen used the separate immutable artefact `prompts/crypto-market-claim-plan-v2.md` with version `crypto-market-claim-plan/v2`.

Prompt v2 preserved every v1 rule and added the canonical validator's source grouping rule:

> A `source_status` claim must describe exactly one source subject. Every cited evidence record in that claim must belong to that same source subject. Use separate claims for separate sources.

## Corrective request envelopes

| Model | Route probe allowance | Full-contract allowance | Reasoning policy |
| --- | ---: | ---: | --- |
| GPT-5.6 Luna | 64 tokens | 4,000 tokens | `none`; temperature omitted |
| DeepSeek V4 Flash | 256 tokens | 12,000 tokens | `high`; reasoning content excluded |
| Qwen3.6 Flash | 64 tokens | 8,000 tokens | explicitly disabled |

The run observed total cost USD 0.0191477293 against a USD 0.10 ceiling.

## Reviewed outcome

- Luna followed the corrected source-status rule but selected a four-operand comparison and an unsupported data-quality limitation.
- DeepSeek completed but ignored the required top-level claim-plan schema, produced 7,582 output tokens and required about 250 seconds.
- Qwen completed within the corrected allowance but returned an invented wrapper and unsupported schema fields.
- Rejected plans remained unscored.
- No model, deployment, automatic generation or publication decision was produced.

## Architectural conclusion

The corrective experiment showed that another full-plan prompt revision would continue asking the model to reproduce deterministic repository semantics.

Phase 6 instead uses:

```text
canonical evidence
  -> deterministic valid claim candidates
  -> deterministic ranking baseline
  -> optional model selection of candidate IDs only
  -> repository-owned plan reconstruction
  -> existing validator and renderer
```

See:

- [`../planning/roadmap/phase-06-deterministic-claim-selection.md`](../planning/roadmap/phase-06-deterministic-claim-selection.md);
- [`notes/simplifying-semantic-claim-plan-pipeline.md`](notes/simplifying-semantic-claim-plan-pipeline.md);
- parent issue #283.

## Preserved evidence and boundary

The corrective runner, configuration, prompt artefacts, schema, validator, renderer, Git history and protected run artefacts remain auditable. Only the manual Actions workflow entry point is removed.

Do not rerun this screen. Any future model evaluation must use the Phase 6 candidate-selection boundary and a separately reviewed case, repeat and cost plan.
