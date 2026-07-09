# Report self-proof evidence contract

Generated report pull requests must carry their own review evidence before they are opened.

This contract supports Phase 3: generated report PRs should be self-proving before downstream PR validation runs. It defines the required evidence fields, allowed statuses, failure semantics, and scope-limit statements that later workflow and PR-body changes must preserve.

## Evidence statuses

Each evidence field should use one of these statuses where a status is needed:

| Status | Meaning | PR creation rule |
| --- | --- | --- |
| `passed` | The proof completed successfully. | Allowed. |
| `not run` | The proof was intentionally not executed, with a reason. | Not allowed for required pre-PR proofs in a normal generated report PR. |
| `not required` | The proof does not apply to this generated report. | Allowed only for explicitly optional proofs. |
| `failed` | The proof failed. | Not allowed; the workflow must fail before opening the PR. |

A generated report PR must not be opened if any required pre-PR proof is `failed` or `not run`.

## Required evidence fields

Every generated report PR body must include these evidence fields.

| Field | Required before PR creation | Expected status for normal generated report PRs | Notes |
| --- | --- | --- | --- |
| Source snapshot | Yes | `passed` | Path to the archived source snapshot used to generate the report. |
| Generated report | Yes | `passed` | Path to the generated Markdown report. |
| Snapshot quality | Yes | `passed` | Snapshot quality must be known and acceptable for the workflow. |
| Required sources | Yes | `passed` | Required source status summary, including `coingecko` and `defillama` where configured. |
| Optional exchange sources | No | `passed` or `not required` | Optional exchange source status summary. Skipped optional sources may be `not required` when the selected cross-check is present. |
| Selected exchange cross-check | Yes | `passed` | The selected exchange cross-check used for consistency evidence. |
| Report validation | Yes | `passed` | Generated Markdown report validation must pass before PR creation. |
| Advice-language check | Yes | `passed` | Prohibited advice-like language classes must be checked before PR creation. |
| Unit tests | Yes | `passed` | Relevant unit tests must pass before PR creation. |
| Static site build | Yes | `passed` | `python -m site_generator` must pass before PR creation. |
| Rendered archive path | Yes | `passed` | The expected `_site/archive/...` output path must exist after the site build. |
| Changed files | Yes | `passed` | Changed files must be restricted to expected generated report paths or explicitly allowed evidence files. |
| `_site` committed | Yes | `passed` | The proof must show generated `_site/` output was not staged or committed. |
| Workflow run | Yes | `passed` | Link or identifier for the workflow run that produced the evidence. |
| Scope limitations | Yes | `passed` | The PR body must state the product and automation boundaries listed below. |

## Failure semantics

The generating workflow must fail before opening a PR if any of these required proofs fails or is missing:

- source snapshot resolution or validation;
- deterministic report generation;
- generated report validation;
- advice-language check;
- relevant unit tests;
- static site build;
- rendered archive path proof;
- changed-file scope validation;
- `_site` exclusion proof;
- evidence body construction.

A normal generated report PR should not use `not run` for required pre-PR proofs. If a proof cannot run because of an environment limitation, the workflow should stop and report the limitation rather than opening a misleading PR.

## Scope limitations required in generated PR bodies

Every generated report PR must state these limitations:

- This PR adds a deterministic Markdown report only.
- This PR does not call an LLM.
- This PR does not provide investment advice or trading recommendations.
- This PR does not publish or deploy the report.
- This PR does not auto-merge.
- This PR does not introduce secrets or paid API keys.
- This PR does not commit generated `_site/` output.

## Review expectation

A self-proving generated report PR is reviewable from its own evidence, but downstream PR validation remains defence in depth. Passing self-proof evidence does not remove the need to respect branch protection, repository governance, review requirements, or CI results.

## Out of scope for this contract

This contract does not implement the evidence builder, workflow sequencing, or PR-body generation. Those are delivered by later Phase 3 issues.
