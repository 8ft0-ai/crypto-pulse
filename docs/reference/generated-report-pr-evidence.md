# Generated report PR evidence

> **Mode:** Reference  
> **Audience:** CryptoPulse workflow developers, operators and reviewers  
> **Outcome:** Look up the evidence fields and failure rules required before a deterministic report pull request is opened.

## Canonical implementation

| Responsibility | Path |
| --- | --- |
| Generation workflow | [`.github/workflows/generate-deterministic-crypto-report.yml`](../../.github/workflows/generate-deterministic-crypto-report.yml) |
| Evidence builder | [`scripts/build_report_pr_evidence.py`](../../scripts/build_report_pr_evidence.py) |
| Changed-file scope validator | [`scripts/validate_generated_report_pr_scope.py`](../../scripts/validate_generated_report_pr_scope.py) |

## Status values

| Status | Meaning | Pull-request rule |
| --- | --- | --- |
| `passed` | The proof completed successfully. | Permitted. |
| `not run` | The proof was intentionally not executed and includes a reason. | Not permitted for a required normal proof. |
| `not required` | The proof does not apply. | Permitted only for an explicitly optional field. |
| `failed` | The proof failed. | The workflow must stop before opening a pull request. |

## Required evidence fields

| Field | Required | Normal status | Evidence |
| --- | --- | --- | --- |
| Source snapshot | Yes | `passed` | Repository-relative path used for generation. |
| Generated report | Yes | `passed` | Generated Markdown path. |
| Snapshot quality | Yes | `passed` | Computed accepted quality state. |
| Required sources | Yes | `passed` | Status summary for every configured required source. |
| Optional exchange sources | Conditional | `passed` or `not required` | Optional cross-check status summary. |
| Selected exchange cross-check | Yes | `passed` | Selected independent price source or explicit none state. |
| Report validation | Yes | `passed` | `validate_crypto_report.py` command and outcome. |
| Advice-language check | Yes | `passed` | Prohibited advice, target, signal and position-language classes checked. |
| Unit tests | Yes | `passed` | `python -m unittest discover -s tests`. |
| Static-site build | Yes | `passed` | `python -m site_generator`. |
| Rendered archive path | Yes | `passed` | Expected `_site/archive/...html` exists. |
| Changed files | Yes | `passed` | Scope restricted to the expected generated report path. |
| `_site` committed | Yes | `passed` | Generated output is not staged or committed. |
| Workflow run | Yes | `passed` | Actions run URL or identifier. |
| Scope limitations | Yes | `passed` | Fixed product and automation boundaries included in the PR body. |

## Failure semantics

The generation workflow must stop before branch or pull-request creation when any required proof fails or is missing, including:

```text
snapshot resolution or validation
deterministic generation
report validation
advice-language validation
unit tests
static-site build
rendered archive path
changed-file scope
_site exclusion
evidence-body construction
```

A normal generated report pull request must not mark a required proof `not run`. An environment limitation is a workflow failure to report, not permission to open a misleading review request.

## Required scope statements

The pull-request body states that the change:

- adds deterministic Markdown report source only;
- does not call an LLM;
- does not provide investment advice or trading recommendations;
- does not publish or deploy the report;
- does not auto-merge;
- introduces no secret or paid API key;
- does not commit generated `_site/` output.

## Pre-PR proof and downstream validation

The generating workflow validates the source, report, tests, site build, rendered path and exact scope before it pushes the automation branch. Pull-request validation then runs again as defence in depth.

Passing self-proof does not bypass branch protection, review requirements or CI. It shows that the generated pull request arrived with enough evidence to be reviewed without relying solely on downstream execution.

## No-op behaviour

If deterministic generation produces no report change, the workflow exits without creating an empty branch or pull request. Evidence does not justify a repository change when there is no material source diff.

For the report content contract, see [Deterministic report schema](deterministic-report-schema.md). For normal issue delivery, see [Deliver a repository slice](../how-to/deliver-a-repository-slice.md).
