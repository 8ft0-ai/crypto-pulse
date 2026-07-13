# Five-model semantic claim-plan catalogue screen

Issue #273 adds a separate catalogue-expansion compatibility screen after the Phase 5 model-evaluation retrospective established that route eligibility, real request compatibility, canonical validation and repeated quality evaluation must be proven in separate stages.

This screen does not replace the pending GPT-5.6 Sol versus Nex N2 Mini calibration in #269. It tests five additional exact OpenRouter slugs against the same governed semantic claim-plan contract.

## Candidate set

The checked-in plan contains exactly:

```text
deepseek/deepseek-v4-flash
openai/gpt-5.6-luna
qwen/qwen3.6-flash
xiaomi/mimo-v2.5-pro
bytedance-seed/seed-2.0-mini
```

The candidate list and catalogue pricing were reviewed against `https://openrouter.ai/api/v1/models` on 13 July 2026. The protected workflow checks the live catalogue again before any route or generation call. A missing model, unsupported structured-output parameter, incompatible reasoning policy, expired slug or price above the checked-in ceiling is recorded as ineligible rather than silently substituted.

## Call and cost boundary

Each model receives at most:

```text
one representative route probe
one real full-contract call
```

The maximum is five route probes and five substantive generations. Candidate ceilings total USD 0.105 and the hard whole-run ceiling is USD 0.15.

The screen is a compatibility experiment, not a benchmark. It does not produce a quality leaderboard or select a deployment model.

## Shared evidence and contract

Every candidate receives the same derived `historical-normal-crosschecked` evidence bundle. Coinbase Exchange USD spot records retain their evidence IDs, source identity, values, units and provenance while the source field `price` is normalised to the canonical measure `price_usd`. The derived bundle receives a recomputed content-addressed bundle ID and the transformation is retained in `evidence-normalisation.json`.

The governed system prompt, strict claim-plan schema, canonical validator, deterministic renderer and case expectation contract remain unchanged.

## Request compatibility policy

Request transforms are explicit and retained per model:

| Model | Temperature | User-role execution message | Reasoning |
| --- | --- | --- | --- |
| DeepSeek V4 Flash | sent | added when absent | `high`, response reasoning excluded |
| GPT-5.6 Luna | omitted | not added | `none` |
| Qwen3.6 Flash | sent | added when absent | explicitly disabled |
| MiMo V2.5 Pro | sent | added when absent | explicitly disabled |
| Seed 2.0 Mini | sent | added when absent | `minimal`, response reasoning excluded |

The workflow verifies that the live catalogue advertises the reviewed reasoning policy. It does not fall back to provider defaults when the plan requests an explicit effort or disabled state.

## Result interpretation

A model passes the screen only when:

- route preflight succeeds;
- the real request completes;
- the exact requested model and an actual provider are retained;
- cross-model fallback remains false;
- the canonical validator accepts the plan;
- the smoke-case expectation gate passes;
- cost metadata is complete and all checked-in ceilings hold.

Rejected or missing plans are unscored. Single-call semantic coverage, materiality and restraint may be retained for an accepted plan, but they are not aggregated into a ranking.

Only a model that passes this screen may be proposed for a separately reviewed repeated multi-case evaluation.

## Trust boundary

The workflow is manual, trusted-main, read-only, protected-environment and artefact-only. It cannot publish analysis, update repository content, select a production model or enable automatic generation.

After merge, dispatch **Semantic plan screen — 5 catalogue candidates** once from `main` and verify the preflight summary before the protected job starts.
