# GPT-OSS candidate-selection quality comparison

> **Mode:** Reference
> **Audience:** CryptoPulse developers, reviewers and governance stakeholders
> **Outcome:** Look up the Phase 9 frozen corpus, exact GPT-OSS/DeepInfra route, staged execution, scoring and evidence boundaries.
> **Status:** Implementation pending independent review; no provider call authorised

Phase 9 provides a bounded, protected comparison between the deterministic candidate selector and one exact model route: `openai/gpt-oss-120b` through pinned `deepinfra`.

## Commands

Secret-free preparation:

```bash
python -m llm_analysis.gpt_oss_quality_comparison_runner prepare \
  --repository-root . \
  --config config/gpt-oss-quality-comparison.yml \
  --output-dir /tmp/gpt-oss-quality-comparison-prepared
```

Protected execution requires `OPENROUTER_API_KEY` and an exact trusted-main SHA:

```bash
python -m llm_analysis.gpt_oss_quality_comparison_runner run \
  --repository-root . \
  --config config/gpt-oss-quality-comparison.yml \
  --prepared-dir /tmp/gpt-oss-quality-comparison-prepared \
  --output-dir /tmp/gpt-oss-quality-comparison \
  --trusted-main-sha <40-character-sha>
```

Do not run the protected command outside separately approved Phase 9 dispatch authority.

## Configuration

`config/gpt-oss-quality-comparison.yml` is strict. Loading fails if any fixed model, provider, corpus, call, retry, repair, route-probe, price, cost, required-candidate, threshold or outcome value changes.

## Preparation artefact

`gpt-oss-quality-comparison-prepared.json` records:

- the regenerated five-case order;
- the deterministic baseline and base prepared-manifest hash;
- case candidate and request identities;
- reviewed-useful candidate IDs;
- deterministic selected IDs;
- required expectation name-to-ID mappings and ordered-set hashes;
- the exact 15-call Stage A/B schedule;
- zero provider calls.

## Protected result artefacts

The result directory contains the availability record, summary, complete planned/attempted record set, per-call request and HTTP evidence, interpreted routing/usage evidence, accepted selections and deterministic renders, reviewer CSV, additions/losses CSV when adjudicable, and deterministic Markdown decision input.

`http-response.json` is written before JSON, identity, metering or model-content interpretation. The interpreted record excludes returned reasoning text and retains only observable reasoning-token counts, finish reason and routing/usage metadata.

## Workflow

`.github/workflows/governed-gpt-oss-quality-comparison.yml` is manual-only, read-only and trusted-main pinned. Preparation runs without the provider secret. Protected execution uses the existing `governed-llm-dry-run` environment and uploads evidence without repository mutation.

No pull-request workflow or test makes a provider call.

## Boundaries

- no provider or model fallback;
- no semantic repair, network retry or route probe;
- no model-authored claims, evidence, values, rationale or prose;
- no report generation, branch write, scheduling or publication;
- no automatic promotion;
- deterministic selection remains the sole active selector until a later reviewed operational decision says otherwise.
