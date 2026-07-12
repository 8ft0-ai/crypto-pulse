# Run a governed LLM dry run

> **Mode:** How-to  
> **Audience:** CryptoPulse operators and reviewers  
> **Outcome:** Run the protected, artefact-only governed-analysis workflow for one checked-in source snapshot and review whether the result was accepted or rejected.

The dry run is a manual proof workflow. It never creates a branch, pull request, report archive entry or deployment. A rejected run is a valid fail-closed outcome and retains diagnostic evidence where execution reached the orchestration layer.

## Before you begin

Confirm that:

- the selected snapshot is already committed under `data/crypto/hourly/` and ends in `_source_snapshot.json`;
- the workflow is dispatched from `main`;
- the protected GitHub environment `governed-llm-dry-run` exists;
- `OPENROUTER_API_KEY` is configured only as an environment secret for that environment;
- the model and provider policy in [`config/llm-generation.yml`](../../config/llm-generation.yml) has been reviewed for the intended input classification.

The current default configuration is a bounded proof profile, not a production approval. Historical model and routing decisions are recorded under [`evaluation/phase-05/`](../../evaluation/phase-05/README.md). The workflow may therefore fail closed because no eligible route exists, the pinned model is unavailable, a provider call fails, or the generated analysis is rejected.

## Select a snapshot

Choose one immutable checked-in source snapshot, for example:

```text
data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json
```

The workflow rejects absolute paths, parent-directory segments and paths outside this pattern:

```text
data/crypto/hourly/**/*_source_snapshot.json
```

The snapshot must also pass the repository snapshot validator before the provider secret becomes available.

## Dispatch the workflow

In GitHub:

1. Open **Actions**.
2. Select **Governed LLM dry run**.
3. Choose **Run workflow**.
4. Select the `main` branch.
5. Enter the repository-relative `snapshot_path`.
6. Start the run.

The equivalent GitHub CLI command is:

```bash
gh workflow run governed-llm-dry-run.yml \
  --ref main \
  -f snapshot_path=data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json
```

If the environment requires reviewers, approve the protected generation job only after confirming that the run uses `main`, the expected snapshot and the intended configuration.

## Review the run summary

Open the completed workflow run and read its Actions summary. Check:

- trusted `main` commit SHA;
- selected snapshot path, SHA-256 and quality status;
- evidence-bundle ID;
- prompt, evidence-schema and analysis-schema versions;
- requested and actual model and provider, where returned;
- same-model provider fallback and cross-model fallback status;
- token usage and returned cost, where available;
- final validation outcome;
- retained artefact filenames.

Do not interpret a successful provider response as accepted analysis. Acceptance requires every offline validation stage to pass.

## Download the review artefact

Download the artefact named:

```text
governed-llm-dry-run-<run-id>-<run-attempt>
```

An accepted run contains:

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

A rejected run should retain diagnostic files such as `validation-report.json`, `run-status.json` and `actions-summary.md`, but must not retain `accepted-analysis.json` or `rendered-preview.md` as accepted output.

## Verify acceptance

Treat the run as accepted only when all of the following agree:

1. the workflow conclusion is successful;
2. `run-status.json` reports acceptance;
3. `validation-report.json` contains no rejecting diagnostics;
4. `accepted-analysis.json` exists;
5. `rendered-preview.md` exists and is repository-rendered rather than model-authored Markdown;
6. generation metadata binds the output to the selected snapshot, evidence bundle, schemas, prompt, model and trusted commit.

If any condition fails, retain the diagnostic artefact for review and do not promote the result manually.

## Review a rejected run

Use the stable failure category and validation stage to identify the boundary that rejected the run. Common causes include:

- invalid snapshot path or snapshot quality;
- missing or malformed secret;
- ineligible provider routing;
- timeout, transport, authentication, billing or provider failure;
- model or cost mismatch;
- malformed completion JSON;
- prepared evidence mismatch;
- unknown evidence reference;
- inconsistent number, unit, timestamp, asset or source;
- unsupported claim semantics;
- advice, forecast, causality, prompt-override or disclaimer-policy violation.

Do not relax privacy, routing, schema or policy controls merely to turn the run green. Correct the underlying configuration or evidence problem through a separate reviewed change.

## Confirm the repository boundary

After the run, confirm that it did not:

- create or update a branch, issue or pull request;
- write to `analysis/` or `reports/`;
- deploy or publish the site;
- expose `OPENROUTER_API_KEY` in artefacts or logs;
- commit generated `_site/` output.

For exact workflow structure and artefact definitions, see [Governed LLM workflows](../reference/governed-llm-workflows.md). For the acceptance stages, see [Offline validation pipeline](../reference/offline-validation-pipeline.md). For the rationale behind the trust boundary, see [Trusted main and secret isolation](../explanation/trusted-main-and-secret-isolation.md).
