# Governed LLM artefact-only dry run

Status: implementation record for issue #186.

This workflow is the first live composition of the Phase 5 evidence contract, the governed OpenRouter client, and the offline validation and rendering pipeline. It is deliberately manual and produces workflow artefacts only. It cannot create or update a branch, commit, issue, pull request, deployment, report archive, or published site.

## Workflow

```text
.github/workflows/governed-llm-dry-run.yml
```

The only trigger is `workflow_dispatch`, with one required input:

```text
snapshot_path
```

The value must be a repository-relative file matching:

```text
data/crypto/hourly/**/*_source_snapshot.json
```

Absolute paths and `..` path segments are rejected before the existing snapshot validator reads the file.

## Trusted-main and secret boundary

The workflow uses three controls together:

1. A guard rejects dispatches whose workflow ref is not `refs/heads/main`.
2. The secret-free preparation job explicitly checks out `main`, validates the selected snapshot, constructs the evidence bundle and records the exact commit SHA.
3. The generation job checks out that exact recorded SHA and uses the protected `governed-llm-dry-run` GitHub environment.

The environment must be configured in repository settings with:

```text
Environment name: governed-llm-dry-run
Deployment branch policy: selected branches -> main only
Environment secret: OPENROUTER_API_KEY
```

`OPENROUTER_API_KEY` must not also exist as a repository-wide or organisation-wide secret available to this repository. Keeping the key only in the protected environment ensures a workflow dispatched or modified on another branch cannot receive it. Optional required reviewers may also be configured on the environment for an additional human approval gate.

The key is injected only into the single `Run governed dry run` step. It is not provided to the preparation job, checkout, dependency installation, artefact upload, Actions summary, or final status step.

Both checkouts use `persist-credentials: false`, and the workflow has only:

```yaml
permissions:
  contents: read
```

## Execution sequence

The preparation job:

1. rejects a non-main dispatch;
2. checks out trusted `main` without persisted credentials;
3. validates the snapshot path boundary;
4. runs `scripts/validate_crypto_snapshot.py` using the current source-quality configuration;
5. constructs and schema-validates a deterministic evidence bundle;
6. uploads the prepared bundle and preparation metadata;
7. exposes the exact trusted commit SHA to the next job.

The generation job:

1. checks out the exact trusted commit SHA;
2. downloads the prepared evidence;
3. independently rebuilds the evidence bundle from the selected snapshot and requires a byte-equivalent canonical bundle;
4. loads the reviewer-visible generation configuration, prompt and schemas;
5. calls the pinned model through `OpenRouterClient`;
6. retains only the raw completion text, never response headers or credentials;
7. runs all offline schema, referential, value, semantic and policy validation stages;
8. renders Markdown only when validation accepts the structured analysis;
9. uploads the review artefacts and writes a concise Actions summary;
10. fails the workflow after artefact upload when generation or validation is rejected.

## Deterministic evidence projection

`llm_analysis/evidence_bundle.py` projects one already-validated snapshot into `crypto-market-evidence-bundle/v1`. Evidence IDs use stable source and entity keys rather than array positions. The projection includes validated market observations, source status and limitations, exchange cross-check values, DeFi totals, stablecoin observations, snapshot quality and generation time.

The source-snapshot SHA-256 hashes the exact checked-in file bytes. The evidence-bundle ID hashes the canonical payload excluding the self-referential `bundle_id` field. The full bundle hash is separately recorded by generation provenance.

Previous generated analysis is never included as evidence.

## Review artefacts

A successful final artefact contains:

```text
evidence-bundle.json
provider-completion.raw.json
accepted-analysis.json
rendered-preview.md
validation-report.json
generation-metadata.json
run-status.json
actions-summary.md
```

`generation-metadata.json` contains the typed provider metadata, complete generation provenance and a secret-free request summary. `provider-completion.raw.json` contains only the provider's completion text. It does not contain request headers, environment variables, the OpenRouter key, or GitHub credentials.

The Actions summary records:

- trusted commit SHA;
- snapshot path, SHA-256 and quality status;
- evidence-bundle ID;
- prompt, analysis-schema and evidence-schema versions;
- requested and actual model and provider;
- provider and cross-model fallback status;
- input, output and total token usage;
- returned cost where available;
- validation outcome;
- retained artefact filenames.

## Fail-closed behaviour

Missing secrets, invalid paths, snapshot validation failures, configuration failures, timeouts, transport/provider failures, malformed provider responses, invalid completion JSON, prepared-bundle mismatches and rejected analysis all produce a failed workflow.

The dry-run command writes `validation-report.json`, `run-status.json` and `actions-summary.md` where execution reached the orchestration layer. It removes or refuses to create `accepted-analysis.json` and `rendered-preview.md` unless every offline validation stage passes. Diagnostic artefacts are uploaded before the workflow is marked failed.

## Preserved boundaries

```text
No schedule or snapshot-merge trigger.
No cross-model fallback.
No report branch or rolling PR.
No commit, issue or pull-request write permission.
No deployment or direct publication.
No LLM-authored Markdown.
No generated _site output committed.
```
