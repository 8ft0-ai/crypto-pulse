# Phase 5 — Governed LLM analysis

Status: shaping.

This is a forward-looking roadmap spec. It describes intended work before delivery. After the phase is delivered, close-out evidence should move into `planning/delivery/` as a completed delivery record.

## Problem statement

CryptoPulse has moved from broad AI-written market reports toward a deterministic evidence spine: source snapshots, validation, deterministic Markdown reports, and static site rendering. That makes the archive safer and more auditable, but the newest deterministic reports can read like evidence tables rather than concise market updates.

The original analyst-style prompt contained useful product intent: concise headlines, plain-English summaries, clear data limitations, source awareness, Australian English, and separation between fact, interpretation, and uncertainty. It also asked the LLM to do unsafe work for this repository: fetch live data, decide sources, infer causes, identify technical levels, generate charts, and frame what traders should watch.

Phase 5 should recover the analysis and readability benefits of the original prompt without allowing the model to become a source of market facts, advice, document formatting, or publication authority.

## Goal

Prove an optional OpenRouter-backed analysis layer that converts an immutable, validated source snapshot into strict structured analysis JSON while preserving deterministic reports as the source of truth.

Repository code should validate every evidence reference, reject unsupported claims, and deterministically render any accepted Markdown. The primary outcome is a manual, reviewable proof loop that records the model, prompt version, schema version, evidence bundle, validation result, generation metadata, and fallback behaviour.

## Non-goals

Phase 5 should not introduce:

```text
No LLM data collection or live web research.
No model-selected market facts, sources, citations, charts, or technical levels.
No free-form LLM Markdown as the source of the report body.
No price targets, trading signals, buy/sell/hold language, portfolio guidance, or investment recommendations.
No LLM rewriting, shortening, moving, or weakening deterministic demo and non-advice disclaimers.
No direct publish from LLM output.
No auto-merge.
No automatic scheduled LLM report generation until manual proofs and evaluation evidence justify it.
No paid model dependency unless explicitly approved.
No committed secrets or API keys.
No committed _site output.
```

This is a constrained analysis and proof phase. The deterministic source snapshot and validated structured analysis remain the authored evidence; repository code owns Markdown rendering; `_site/` remains disposable generated output.

## Target workflow

The target workflow keeps the OpenRouter step optional, manual-first, and fail-safe.

```text
validated source snapshot
compact evidence bundle creation
OpenRouter structured-analysis call using a pinned free model slug
strict JSON/schema validation
evidence_id existence and claim-support validation
advice, hallucination, numeric-consistency, and prompt-injection checks
deterministic Markdown rendering from accepted JSON
report PR with generation metadata and validation proof
fail closed with diagnostics when unavailable or rejected
```

The first implementation should be `workflow_dispatch` only. It should accept one historical or current source snapshot, call OpenRouter from trusted `main` workflow code, validate the structured response, and open or update a report PR only when all checks pass.

The LLM should not receive credentials, GitHub tokens, or repository secrets. It should receive only the curated evidence bundle and generation instructions. Prompt text should clearly separate repository instructions from untrusted source data.

Proposed repository structure:

```text
llm_analysis/
  __init__.py
  client.py
  prompt.py
  schema.py
  validate.py
  render.py
prompts/
  crypto-market-analysis-v1.md
schemas/
  crypto-market-analysis-v1.json
config/
  llm-generation.yml
```

The model and provider policy should live in configuration, not in workflow YAML or business logic.

Example configuration shape:

```yaml
provider: openrouter
model: nvidia/nemotron-3-super-120b-a12b:free
fallback_models:
  - google/gemma-4-26b-a4b-it:free
  - qwen/qwen3-next-80b-a3b-instruct:free
temperature: 0.2
max_output_tokens: 4000
prompt_version: crypto-market-analysis-v1
schema_version: crypto-market-analysis-v1
provider_policy:
  require_parameters: true
  data_collection: deny
  zdr: true
  allow_fallbacks: true
```

The workflow should avoid `openrouter/free` and `openrouter/auto` for proof-grade generation because variable routing weakens reproducibility and makes two identical snapshots harder to compare.

Candidate structured output fields:

```text
headline
market_summary
key_observations[] with claim, evidence_ids, and confidence
risks_and_limitations[]
data_quality_notes[]
source_evidence_note
```

Initial model preference:

```text
primary: nvidia/nemotron-3-super-120b-a12b:free
fallback: google/gemma-4-26b-a4b-it:free
fallback: qwen/qwen3-next-80b-a3b-instruct:free
fallback: tencent/hy3:free
fallback: openai/gpt-oss-20b:free
```

Each observation should reference explicit `evidence_ids` from the evidence bundle unless it is classified as qualitative interpretation. Numeric comparative claims should be machine-checkable where practical.

Every generated report should capture provenance metadata such as:

```text
provider
requested_model
actual_model
prompt_version
schema_version
source_snapshot
source_snapshot_sha256
generated_at
temperature
input_tokens
output_tokens
generation_id
prompt_hash
completion_hash
estimated_cost
```

## Acceptance gates

Phase 5 is complete when:

- [ ] deterministic report generation still works with no OpenRouter secret configured;
- [ ] OpenRouter credentials are read only from repository or organisation secrets;
- [ ] the chosen model slug and fallback order are pinned or recorded in generated evidence;
- [ ] the prompt template is versioned and reviewer-visible;
- [ ] the JSON schema is versioned and reviewer-visible;
- [ ] the evidence bundle includes only validated snapshot/report fields and required disclaimer boundaries;
- [ ] LLM output is JSON-schema validated before use;
- [ ] every `evidence_id` in LLM output exists in the evidence bundle;
- [ ] numeric values, timestamps, source names, asset names, and comparative claims in LLM output are traceable to the evidence bundle;
- [ ] banned advice, recommendation, trading-signal, target-price, and unsupported-causality language is rejected;
- [ ] source-data prompt-injection boundaries are documented and tested;
- [ ] failed, unavailable, timed-out, or rejected LLM output fails closed and opens no LLM report PR;
- [ ] deterministic non-LLM generation remains unblocked by LLM failures;
- [ ] a generated PR or artefact records prompt version, schema version, model/provider identifier, evidence bundle path, raw model output, validation result, token usage, cost metadata where available, and fallback status;
- [ ] the first LLM workflow is manual-only and runs only trusted code from `main`;
- [ ] `openrouter/free` and `openrouter/auto` are not used as production defaults;
- [ ] public-facing demo, AI-generated, not-financial-advice, not-investment-research, not-recommendation, and not-trading-signal language is preserved;
- [ ] `python -m site_generator` still builds the site if any rendering changes are included;
- [ ] PR validation passes;
- [ ] generated `_site/` output is not committed.

## Proposed implementation slices

Use linked issues rather than relying on native GitHub sub-issues.

```text
1. Parent Phase 5 issue — Governed LLM analysis.
2. Define the evidence-bundle schema, evidence ID convention, JSON schema, and prompt contract.
3. Add OpenRouter configuration, provider-routing policy, model-selection policy, and secret handling.
4. Add a manual-only LLM analysis workflow that runs trusted code from `main`.
5. Generate structured analysis JSON from one selected validated snapshot.
6. Add validation checks for schema, evidence IDs, claim support, numeric consistency, prompt-injection boundaries, and advice leakage.
7. Deterministically render Markdown from accepted structured analysis.
8. Prove fail-closed behaviour with missing secret, timeout, invalid JSON, unsupported evidence reference, unsupported numerical claim, and policy violation cases.
9. Build a small historical evaluation corpus and record initial model-selection evidence.
10. Record Phase 5 proof and close-out evidence.
```

## Risks and mitigations

### Risk: The LLM invents market facts or sources

Mitigation: provide only a compact evidence bundle, disable model-side research, require strict JSON output, reject unknown `evidence_ids`, reject untraceable names/numbers/timestamps, and keep source references deterministic.

### Risk: The prose becomes financial advice or trading guidance

Mitigation: ban target prices, buy/sell/hold language, trading signals, portfolio actions, and unsupported forecasts. Treat validation failure as a hard fallback to deterministic-only output.

### Risk: Free model availability or behaviour changes

Mitigation: record exact model slug and provider response metadata where available, maintain an explicit fallback order, and never block deterministic reports solely because optional prose is unavailable.

### Risk: Variable routing undermines reproducibility

Mitigation: do not use `openrouter/free` or `openrouter/auto` for proof-grade generation. Use explicit `provider/model:free` slugs and record requested and actual model metadata in artefacts and PR evidence.

### Risk: Secrets leak into logs or committed files

Mitigation: read `OPENROUTER_API_KEY` only from Actions secrets or local environment, never write it to artefacts, and keep raw request/response evidence scrubbed of credentials.

### Risk: Pull-request code exfiltrates secrets

Mitigation: run the LLM workflow only from trusted code on `main`, avoid exposing OpenRouter secrets to arbitrary pull-request workflows, and keep PR-creation permissions limited to the job that needs them.

### Risk: Structured JSON passes syntax checks but makes unsupported claims

Mitigation: require explicit evidence IDs for observations, validate ID existence, add deterministic checks for supported comparative claims, and fail closed when claim support cannot be established.

### Risk: Cost or token use becomes uncontrolled

Mitigation: cap input size, output tokens, retries, and model price; record token usage and estimated cost; define deterministic truncation rules before any automated schedule is enabled.

### Risk: The phase expands into news ingestion, charting, model bake-offs, or technical analysis

Mitigation: park those ideas in the roadmap backlog unless they are required for the manual proof. Phase 5 only proves governed structured analysis over existing validated evidence.

## Definition of done

The phase is complete when:

- [ ] the parent Phase 5 issue and linked child issues exist;
- [ ] implementation PRs are merged;
- [ ] proof evidence records at least one accepted structured-analysis report PR and at least one rejected/fail-closed case;
- [ ] a small historical evaluation corpus records initial model-selection evidence;
- [ ] close-out evidence is added to the parent issue;
- [ ] a delivery record is added under `planning/delivery/`;
- [ ] `planning/delivery-log.md` is updated;
- [ ] `planning/delivery/delivery.yaml` is updated, or explicitly marked not applicable;
- [ ] `planning/delivery/graph.md` is regenerated when `delivery.yaml` changes;
- [ ] generated `_site/` output is not committed.

## Close-out PR checklist

For the PR that closes this phase:

- [ ] Update `planning/delivery/phase-05-governed-llm-analysis.md`.
- [ ] Update `planning/delivery-log.md`.
- [ ] Update `planning/delivery/delivery.yaml`.
- [ ] Regenerate `planning/delivery/graph.md`.
- [ ] Update `planning/roadmap/` only if roadmap intent or next-phase direction changed.
- [ ] Confirm raw Markdown reports remain the source of truth.
- [ ] Confirm generated `_site/` output is not committed.

## Follow-on delivery record

At close-out, create:

```text
planning/delivery/phase-05-governed-llm-analysis.md
```

The completed delivery record should explain what was allowed into the LLM evidence bundle, which evidence ID convention and OpenRouter model policy were used, what validation proved, what artefacts were produced, which fail-closed cases were exercised, what evaluation evidence supported the model choice, and what publication boundaries were preserved.
