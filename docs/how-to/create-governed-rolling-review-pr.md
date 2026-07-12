# Create a governed rolling-review pull request

> **Mode:** How-to  
> **Audience:** CryptoPulse operators and reviewers  
> **Outcome:** Run the protected governed-analysis publication workflow for one checked-in snapshot and review the controlled rolling pull request when an accepted result produces a material change.

The rolling-review workflow does not give the model publication authority. It accepts structured JSON only after offline validation, rebuilds repository-owned source files from trusted code, proves the repository build and then opens or updates one controlled pull request. It does not merge or publish that pull request automatically.

## Before you begin

Complete the prerequisites from [Run a governed LLM dry run](run-governed-llm-dry-run.md). In addition, confirm that:

- the intended model and provider profile has been explicitly approved for this use;
- the selected snapshot is suitable for a review PR rather than an evaluation-only experiment;
- no unrelated change is expected on the controlled rolling branch;
- you have permission to dispatch the workflow and review the resulting pull request.

Historical evaluation decisions under [`evaluation/phase-05/`](../../evaluation/phase-05/README.md) may block a configuration from producing an accepted rolling result. Do not treat the existence of the workflow as approval to weaken those decisions.

## Select a source snapshot

Use one committed source snapshot matching:

```text
data/crypto/hourly/YYYY/MM/DD/<time>_source_snapshot.json
```

For example:

```text
data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json
```

Do not use an evaluation-only mutation or an uncommitted local file. The workflow validates both the path and snapshot before provider access.

## Dispatch the workflow

In GitHub:

1. Open **Actions**.
2. Select **Governed LLM review PR**.
3. Choose **Run workflow**.
4. Select the `main` branch.
5. Enter the repository-relative `snapshot_path`.
6. Start the run.

The equivalent GitHub CLI command is:

```bash
gh workflow run governed-llm-review-pr.yml \
  --ref main \
  -f snapshot_path=data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json
```

Approve a protected generation job only after confirming the trusted branch, snapshot and configuration.

## Follow the three job boundaries

The workflow separates responsibilities:

1. **Prepare** validates the snapshot and creates deterministic evidence without the provider secret.
2. **Generate** receives the environment secret, calls the pinned model and runs offline acceptance without repository write permission.
3. **Prove and publish** receives repository write permission but no provider secret, reproduces the accepted files, runs repository proof and updates the rolling branch.

A failure in either of the first two stages must prevent the write-capable stage from publishing source files.

## Check whether a material change exists

A successful accepted generation can still produce no pull-request update when the intended source files do not materially differ from the current rolling branch or `main`.

Read the workflow summary for:

```text
Rolling branch: automation/governed-llm-analysis-rolling
Material change: true | false
Pull request: <number> | not created or unchanged
```

An unchanged result is not an error and must not create an empty commit.

## Review the controlled pull request

When a material change exists, the workflow opens or updates the single pull request titled:

```text
Update governed LLM analysis
```

The pull request must target `main` from:

```text
automation/governed-llm-analysis-rolling
```

For a snapshot such as:

```text
data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json
```

review exactly these source-controlled outputs:

```text
analysis/crypto/hourly/2026/07/08/governed/1742_AEST_analysis.json
analysis/crypto/hourly/2026/07/08/governed/1742_AEST_provenance.json
reports/crypto/hourly/2026/07/08/governed/1742_AEST_crypto_market_intelligence.md
```

The accepted analysis JSON is canonical. The provenance sidecar binds it to the source snapshot, evidence bundle, schemas, prompt, trusted commit, model/provider metadata, generation parameters, usage, cost, routing state and validation result. The Markdown report must reproduce the deterministic renderer output.

Raw provider completion text must remain in the workflow artefact and must not appear in the changed-file list.

## Verify the pre-push proof

Confirm the workflow completed all of these checks before pushing:

- selected snapshot validation;
- prepared evidence integrity;
- complete offline analysis acceptance;
- deterministic renderer reproduction;
- exact manifest-declared changed-file scope;
- `python -m unittest discover -s tests`;
- `python -m site_generator`;
- existence of the expected rendered report under `_site/archive/`;
- absence of staged `_site/` files.

The normal pull-request validation workflow remains defence in depth. It is not a substitute for the workflow's pre-push proof.

## Review the reader-facing report

Check that the report:

- preserves the AI-generated demo and non-advice boundaries;
- contains only repository-rendered structure;
- includes no unsupported facts, causes, forecasts, targets, signals or portfolio actions;
- traces each analytical claim to evidence IDs;
- represents degraded or missing data as a limitation rather than a market conclusion;
- matches the canonical accepted JSON and provenance record.

## Merge only through normal review

Do not merge merely because the generation workflow succeeded. Wait for required pull-request checks and repository review policy. The rolling workflow does not auto-merge and does not publish directly.

If the pull request is rejected, close or correct it through normal reviewed repository work. Do not edit generated source files manually to bypass a failed evidence or validation boundary.

For precise branch, permission and artefact behaviour, see [Governed LLM workflows](../reference/governed-llm-workflows.md). For the source contract, see [Governed analysis contract](../reference/governed-analysis-contract.md). For the architectural rationale, see [Evidence and analysis boundary](../explanation/evidence-and-analysis-boundary.md).
