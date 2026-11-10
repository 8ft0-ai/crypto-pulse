# Governed LLM workflows

> **Mode:** Reference  
> **Audience:** CryptoPulse operators, workflow maintainers and reviewers  
> **Outcome:** Look up triggers, inputs, permissions, job boundaries, artefacts and repository effects for the governed dry-run and rolling-review workflows.

## Workflow summary

| Property | Dry run | Rolling review |
| --- | --- | --- |
| Workflow | [`.github/workflows/governed-llm-dry-run.yml`](../../.github/workflows/governed-llm-dry-run.yml) | [`.github/workflows/governed-llm-review-pr.yml`](../../.github/workflows/governed-llm-review-pr.yml) |
| Trigger | `workflow_dispatch` | `workflow_dispatch` |
| Required input | `snapshot_path` | `snapshot_path` |
| Required workflow ref | `main` | `main` |
| Provider environment | `governed-llm-dry-run` | `governed-llm-dry-run` |
| Provider secret | `OPENROUTER_API_KEY` | `OPENROUTER_API_KEY` |
| Primary output | Review artefact | Accepted source files on a controlled rolling PR |
| Repository write permission | None | Prove-and-publish job only |
| Direct deployment | No | No |
| Auto-merge | No | No |

## Input contract

Both workflows accept one repository-relative path:

```text
data/crypto/hourly/**/*_source_snapshot.json
```

The path must not be absolute or contain `..`. The selected file must pass [`scripts/validate_crypto_snapshot.py`](../../scripts/validate_crypto_snapshot.py) before provider access.

## Trusted commit contract

Both workflows:

1. reject dispatches whose workflow ref is not `refs/heads/main`;
2. check out current `main` in a secret-free preparation job;
3. record the exact trusted commit SHA;
4. build the evidence bundle from that commit;
5. check out the same SHA in the protected generation job;
6. verify the checked-out SHA before generation.

The generation job does not execute code from an arbitrary pull-request branch.

## Dry-run jobs

### `guard`

- Requires a `main` dispatch.
- Receives no provider secret.
- Has no repository write permission.

### `prepare`

- Checks out trusted `main` with `persist-credentials: false`.
- Records the trusted SHA.
- Validates the input path and source snapshot.
- Builds and schema-checks the evidence bundle.
- Uploads the prepared evidence for seven days.
- Receives no provider secret.

Prepared artefact name:

```text
governed-llm-prepared-<run-id>-<run-attempt>
```

### `generate`

- Checks out the exact trusted SHA with `persist-credentials: false`.
- Uses the protected `governed-llm-dry-run` environment.
- Exposes `OPENROUTER_API_KEY` only to the generation command.
- Rebuilds and compares the evidence bundle.
- Calls the configured provider and model.
- Runs offline acceptance and deterministic rendering.
- Publishes the Actions summary and review artefact even after a handled rejection.
- Marks the workflow failed when generation or validation is rejected.

Review artefact name:

```text
governed-llm-dry-run-<run-id>-<run-attempt>
```

Retention: 14 days.

## Dry-run artefacts

An accepted dry-run artefact contains:

| File | Contents |
| --- | --- |
| `evidence-bundle.json` | Canonical deterministic evidence passed to the provider. |
| `provider-completion.raw.json` | Provider completion text only; no request headers or credentials. |
| `accepted-analysis.json` | Canonical accepted structured analysis. |
| `rendered-preview.md` | Repository-rendered Markdown preview. |
| `validation-report.json` | Ordered acceptance diagnostics and stage outcomes. |
| `generation-metadata.json` | Typed provider metadata, provenance and secret-free request summary. |
| `run-status.json` | Orchestration outcome. |
| `actions-summary.md` | Reviewer summary used in GitHub Actions. |

Rejected runs must not leave `accepted-analysis.json` or `rendered-preview.md` as accepted output. Diagnostic files are retained where execution reached the orchestration layer.

## Rolling-review jobs

The rolling workflow uses the same `guard`, preparation and protected generation boundaries. Its write-capable stage is separate.

### `prove-and-publish`

Permissions:

```yaml
contents: write
pull-requests: write
```

This job receives no OpenRouter secret. It:

1. checks out the exact trusted SHA with push capability;
2. downloads the scrubbed accepted-generation artefact;
3. uses [`llm_analysis/publication.py`](../../llm_analysis/publication.py) to reproduce the source-controlled files;
4. compares the intended files with the existing rolling branch or trusted `main`;
5. exits without a commit when there is no material change;
6. stages only manifest-declared paths;
7. validates the exact changed-file scope;
8. runs the complete unit-test suite;
9. builds the static site;
10. verifies the expected rendered report exists;
11. rejects staged `_site/` paths;
12. force-updates the controlled branch with lease protection;
13. opens or updates the single rolling pull request.

## Rolling branch and pull request

```text
Branch: automation/governed-llm-analysis-rolling
Pull-request title: Update governed LLM analysis
Base: main
```

Each successful material update starts from the exact trusted `main` commit. The workflow must not create an empty commit or duplicate pull request.

## Source-controlled output paths

For:

```text
data/crypto/hourly/YYYY/MM/DD/<time>_source_snapshot.json
```

the workflow writes:

```text
analysis/crypto/hourly/YYYY/MM/DD/governed/<time>_analysis.json
analysis/crypto/hourly/YYYY/MM/DD/governed/<time>_provenance.json
reports/crypto/hourly/YYYY/MM/DD/governed/<time>_crypto_market_intelligence.md
```

The changed-file manifest must contain exactly those three paths for the selected snapshot.

Raw provider completion text remains a workflow artefact and is not committed.

## Pre-push validation

Before the rolling branch is updated, the workflow proves:

```text
snapshot path and content accepted
prepared evidence reproduced exactly
structured analysis accepted by every offline stage
Markdown reproduced by the deterministic renderer
changed-file scope equals the publication manifest
python -m unittest discover -s tests passes
python -m site_generator passes
expected rendered report exists
_site is not staged
```

Normal pull-request validation runs again after the PR is opened or updated.

## Failure and no-op behaviour

| Condition | Result |
| --- | --- |
| Non-main dispatch | Workflow fails before checkout of generation code. |
| Invalid path or snapshot | Workflow fails before provider access. |
| Missing secret or provider failure | Generation fails; no publication job output. |
| Rejected analysis | Diagnostic artefact retained; no accepted source files. |
| Accepted analysis with no material source change | No commit or pull-request update. |
| Failed tests, site build, rendered-path check or scope check | No branch push. |
| Successful accepted material change | Controlled rolling branch and PR are opened or updated. |

## Fixed boundaries

Neither workflow:

- schedules itself;
- enables cross-model fallback;
- commits raw provider output;
- accepts model-authored Markdown;
- deploys or publishes directly;
- merges a pull request;
- commits `_site/`.

For operating steps, see [Run a governed LLM dry run](../how-to/run-governed-llm-dry-run.md) and [Create a governed rolling-review pull request](../how-to/create-governed-rolling-review-pr.md).
