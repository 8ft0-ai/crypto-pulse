# Corrective semantic claim-plan screen — run 29285569716

Status: reviewed Phase 5 evaluation evidence.

Source workflow run: [29285569716](https://github.com/8ft0-ai/crypto-pulse/actions/runs/29285569716)  
Trusted `main` SHA: `3d4df194e8fc6851d97467b75aaca2200718876d`  
Plan: `semantic-plan-model-corrective-screen/v1`  
Prompt: `crypto-market-claim-plan/v2`

## Purpose

The run gave GPT-5.6 Luna, DeepSeek V4 Flash and Qwen3.6 Flash one representative route probe and one full-contract attempt over the same normalised `historical-normal-crosschecked` evidence bundle.

It corrected three limitations from the earlier catalogue screen:

- prompt v2 made the one-source-subject-per-`source_status` rule explicit;
- DeepSeek received a 256-token reasoning-aware route probe;
- Qwen received an 8,000-token full-contract allowance.

The run was a compatibility screen, not a leaderboard or production decision.

## Integrity and cost

```text
Route probes completed:           3 / 3
Full-contract calls completed:    3 / 3
Observed total cost:              USD 0.0191477293
Whole-run ceiling:                USD 0.10
Deployment selection:             not performed
Quality leaderboard:              not produced
Automatic generation:             false
Publication:                      false
```

All three models completed with `finish_reason: stop`. Rejected plans remained unscored with null semantic coverage, materiality and restraint.

## Results

| Model | Provider | Route | Full contract | Validator | Cost including probe | Latency |
| --- | --- | --- | --- | --- | ---: | ---: |
| `openai/gpt-5.6-luna` | OpenAI | Passed | Rejected | Not accepted | USD 0.013833 | 4,091 ms |
| `deepseek/deepseek-v4-flash` | DeepInfra | Passed | Rejected | Not accepted | USD 0.0021066043 | 250,507 ms |
| `qwen/qwen3.6-flash` | Alibaba | Passed | Rejected | Not accepted | USD 0.003208125 | 6,369 ms |

### GPT-5.6 Luna

Luna returned the expected top-level claim-plan shape and followed the new one-source status rule, but the semantic validator rejected two claims:

```text
comparison_operand_count
  comparison intent requires exactly two evidence identifiers

data_quality_support_missing
  data-quality limitations require explicit missing, failed, stale,
  degraded, skipped, warning, incomplete or conflicting evidence
```

The plan selected one four-operand comparison and treated Coinbase `covered_symbols` evidence as a data-quality limitation. The first diagnostic revealed another validator rule that was not explicit in prompt v2; the second was a direct instruction-adherence failure. Luna selected 18 claims, so restraint also remained a concern even though soft scoring was correctly withheld after rejection.

Reviewed interpretation: Luna was the strongest full-plan candidate, but another prompt revision and paid retry would continue making the model reproduce deterministic repository rules.

### DeepSeek V4 Flash

The corrected probe proved that the route could complete. The full call then returned 7,582 output tokens and required about 250 seconds. The result did not conform to the canonical top-level claim-plan schema.

Missing required properties included:

- `analysis_order`;
- `claim_plan_version`;
- `evidence_bundle_id`;
- `prompt_version`;
- `sections`.

The response introduced a top-level `claims` property that the schema does not permit. The run also recorded provider fallback between the route probe and the full call.

Reviewed interpretation: DeepSeek V4 Flash does not advance on the full-plan path under the evaluated request and routing configuration.

### Qwen3.6 Flash

The 8,000-token allowance resolved the earlier truncation. Qwen completed after 1,435 output tokens but returned an invented top-level `plan` wrapper rather than the required claim-plan object.

Missing required properties included:

- `analysis_order`;
- `claim_plan_version`;
- `evidence_bundle_id`;
- `prompt_version`;
- `sections`.

Reviewed interpretation: Qwen3.6 Flash does not advance on the full-plan path under the evaluated Alibaba route.

## Architectural conclusion

The run completed the corrective experiment but did not justify another full claim-plan prompt revision.

The failures show that the model was still being asked to act as a semantic compiler: construct intent, operands, relation, source/data-quality eligibility, sections and ordering while satisfying repository rules that can be enforced deterministically.

The approved direction is therefore:

```text
canonical evidence
  -> deterministic valid claim candidates
  -> deterministic baseline ranking
  -> optional model selection of candidate IDs only
  -> repository-owned plan reconstruction
  -> existing validator and renderer
```

This decision is developed in:

- [`../../docs/notes/simplifying-semantic-claim-plan-pipeline.md`](../../docs/notes/simplifying-semantic-claim-plan-pipeline.md);
- [`../../docs/notes/semantic-claim-selection-implementation-patterns.md`](../../docs/notes/semantic-claim-selection-implementation-patterns.md);
- [`../../planning/roadmap/phase-06-deterministic-claim-selection.md`](../../planning/roadmap/phase-06-deterministic-claim-selection.md).

## Decision boundary

- No candidate from this screen advances to repeated full-plan evaluation.
- Issue #275 is complete because the planned corrective screen ran and was reviewed.
- Issue #269 is superseded; the GPT-5.6 Sol/Nex full-plan calibration should not run.
- Historical prompts, schemas, runners, plans and protected artefacts remain auditable.
- The corrective and final full-plan manual workflows may be removed from the Actions UI.
- No model has been selected.
- Automatic generation and publication remain disabled.
