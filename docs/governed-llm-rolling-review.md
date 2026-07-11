# Governed LLM rolling review PR

Status: implementation record for issue #187.

The rolling review workflow promotes only accepted structured analysis into repository source files. It does not give the model publication authority. The model returns JSON; repository code validates it, reproduces the deterministic Markdown, proves the repository build, and only then updates one controlled review branch and pull request.

## Manual entry point

Workflow: `.github/workflows/governed-llm-review-pr.yml`

Input:

```text
snapshot_path: data/crypto/hourly/YYYY/MM/DD/<time>_source_snapshot.json
```

The workflow is `workflow_dispatch` only and rejects execution when the selected workflow ref is not `main`.

## Trust and secret boundaries

The preparation job checks out trusted `main`, validates the selected snapshot and records the exact commit SHA. The generation job checks out that SHA and is the only job attached to the protected `governed-llm-dry-run` environment. `OPENROUTER_API_KEY` appears only on the generation command.

The publishing job has GitHub write permission but no OpenRouter secret. It receives only the scrubbed dry-run artefact, rebuilds the accepted output using trusted repository code, runs all tests and the static-site build, and stages only the manifest-declared source files.

## Source-controlled paths

For a snapshot such as:

```text
data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json
```

the workflow writes:

```text
analysis/crypto/hourly/2026/07/08/governed/1742_AEST_analysis.json
analysis/crypto/hourly/2026/07/08/governed/1742_AEST_provenance.json
reports/crypto/hourly/2026/07/08/governed/1742_AEST_crypto_market_intelligence.md
```

The analysis file is the canonical accepted structured response. The provenance sidecar binds it to the immutable source snapshot, evidence bundle, deterministic report, prompt and schema versions, requested and actual model/provider, generation parameters, usage, cost, routing state, generation identifiers and validation result.

The Markdown report has repository-generated front matter followed by the exact deterministic renderer output. Raw provider text remains a workflow artefact and is never staged.

## Rolling branch and PR

```text
Branch: automation/governed-llm-analysis-rolling
PR title: Update governed LLM analysis
Base: main
```

Each successful run starts from the exact trusted `main` commit. If the intended source files do not materially differ from the current rolling branch or `main`, the workflow exits without an empty commit or duplicate PR. Otherwise it force-updates the controlled branch with lease protection and opens or updates the single open PR for that branch.

## Pre-push proof

Before any push, the workflow proves:

```text
selected snapshot validation
prepared evidence integrity
provider result accepted by every offline validation layer
deterministic renderer reproduction
exact three-file changed scope
full repository unit tests
python -m site_generator
expected rendered report exists
_site is not staged
```

Downstream pull-request validation remains defence in depth rather than the first proof source.

## Preserved boundaries

```text
No schedule or snapshot-merge trigger.
No raw provider output committed.
No model-generated Markdown.
No direct publication.
No auto-merge.
No cross-model fallback.
No paid-model requirement.
No committed _site output.
```
