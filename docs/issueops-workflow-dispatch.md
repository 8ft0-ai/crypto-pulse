# Reusable IssueOps workflow dispatcher

This document describes the source-controlled implementation of issue #356. The dispatcher is a repository control plane for converting one exact, reviewed issue comment into one exact `workflow_dispatch` request. It is not protected execution authority by itself and it never receives model/provider secrets.

## Permanent boundary

The listener is `.github/workflows/issueops-workflow-dispatch.yml`. It reacts only to newly created issue comments. The registry is `.github/issueops-workflow-dispatch.yml` and contains no active authorisation after dispatcher implementation. The file uses canonical JSON syntax, which is a YAML 1.2 subset, so the privileged runtime uses only the Python standard library and does not install a YAML package from the network.

An executable authorisation is a separately reviewed schema-v2 record. It freezes the governing issue and command, immutable owner identity, target workflow numeric ID/path/hash, fixed inputs, one-attempt limit, validity window, execution-tag ruleset identity, dispatcher workflow hash and the `dispatch_attestation_v1` predicate type. Comment text cannot choose a workflow, ref, input, model, provider or budget.

## Exact-event activation

The dispatcher checks out the exact `issue_comment` event SHA with its first parent. A matching enabled record is executable only when that selected record is absent from, or materially different from, the first-parent registry. An unchanged enabled record carried forward from an earlier commit is rejected. This binds activation to the exact reviewed event snapshot rather than allowing stale authority to survive unrelated `main` changes.

The dispatcher also requires `github.workflow_sha == github.sha`, `github.run_attempt == 1`, the exact owner login and immutable numeric user ID, `OWNER` association, governing issue, exact command and dispatcher-workflow hash.

## One-time consumption

For authorisation `<id>` at created-event source commit `<S>`, the runtime derives:

```text
issueops/dispatch/<id>--sha-<S>
refs/tags/issueops/dispatch/<id>--sha-<S>
```

The tag is a lightweight reference directly to `<S>`. The side-effect job validates the target workflow and exact runtime-observable execution-tag ruleset, rejects a pre-existing tag, then re-fetches and revalidates the triggering comment immediately before tag creation. The live comment must retain its exact issue relationship, body, actor, association and unedited timestamps.

Exactly one `POST /git/refs` is available in dispatcher code. Only HTTP `201` with a verifiable returned ref followed by exact ref read-back owns continuation. Timeout, reset, malformed/lost success data or any other ambiguous create result never grants continuation and never causes a second create. The dispatcher performs exactly one bounded read-only lookup of the canonical ref for classification only: an existing exact ref is classified as consumed, a conflicting ref as consumed/conflicted, and an absent or unavailable ref still ends the run without dispatch.

After an unambiguous create winner and exact tag read-back, the dispatcher fetches and validates the same frozen execution-tag ruleset again before the sole workflow-dispatch write. Any post-consumption drift in the observable ruleset state fails closed with zero dispatch attempts. The already-created tag remains consumed; failure never restores authority.

The separately provisioned v1 ruleset must expose exactly this runtime condition:

```text
include: refs/tags/issueops/dispatch/*
exclude: []
```

It must be active for tags, restrict update and deletion, and must not restrict creation. Runtime deliberately does not infer that omitted `bypass_actors` means empty; complete bypass-actor proof remains a separately governed provisioning review.

## Dispatch and run binding

After consumption and the post-consumption ruleset re-check, exactly one Actions write endpoint is available:

```text
POST /actions/workflows/{frozen_numeric_id}/dispatches
```

The ref is the derived execution tag and inputs are the frozen source-controlled map. API version `2026-03-10` must return HTTP `200` with direct target run identity. The dispatcher never infers a run from timestamps, actor, ref or search results and never retries an uncertain dispatch.

The returned run is fetched at attempt 1 and must match the frozen workflow ID/path, event `workflow_dispatch`, exact execution tag and exact source SHA.

## Signed receipt

A separate job in the same canonical dispatcher workflow revalidates the exact target run and creates deterministic JSON subject and predicate files. Both use key-sorted compact UTF-8 JSON with one trailing LF.

The canonical subject contains exactly:

```text
schema
repository
repository_id
authorisation_id
authorisation_sha
execution_ref
target_workflow_id
target_workflow_path
target_run_id
target_ref
target_sha
```

Its `schema` is `dispatch_attestation_v1`. Richer owner, comment, record-hash and dispatcher-run audit bindings live in the custom predicate, which also has `schema: dispatch_attestation_v1`, `target_event: workflow_dispatch` and the frozen-input hash.

The workflow signs with `actions/attest` pinned to immutable commit `1e69f48acb82d1966a394da916b4c1698aa569d6`. The signing job has read-only Actions/contents access plus only OIDC and attestation writes. It has no `actions: write`, no `contents: write`, no protected environment and no provider secret.

## Frozen executable dependencies

Every external action in the dispatcher is pinned by full commit SHA:

```text
actions/checkout   11d5960a326750d5838078e36cf38b85af677262
actions/setup-python a26af69be951a213d495a4c3e4e4022e16d87065
actions/attest     1e69f48acb82d1966a394da916b4c1698aa569d6
```

The privileged runtime installs no Python package from the network. Registry parsing and workflow-trigger inspection use standard-library-only code.

## Reruns and failures

Every dispatcher resolution, side-effect and signing boundary requires attempt 1 and the canonical source/workflow SHA. A workflow or job rerun cannot legitimately create another execution tag, issue another target dispatch or sign a new receipt.

A later edit or deletion after successful tag consumption does not restore, revoke or duplicate consumed authority. API timeouts, resets, 4xx/5xx responses, malformed direct dispatch success data, signing failure or target failure never cause an automatic second dispatch. Ambiguous tag creation is reconciled read-only for classification only and likewise never produces a blind retry or continuation winner.

## Target-side verification remains separately governed

This implementation does not modify `.github/workflows/governed-gpt-oss-quality-comparison.yml`, repository rulesets, the `governed-llm-dry-run` environment or any Phase 9 authorisation.

Before a protected target can use this dispatcher, a separate reviewed stage must provision and review the immutable tag ruleset and environment tag policy, harden the target with its attempt-1 provenance gate and pinned `gh` v2.97.0 verifier contract from issue #356, add one reviewed authorisation record and only then create an authorised command.

Tests use fake transport only. They do not create a real tag, dispatch a workflow, write an attestation or call a provider.
