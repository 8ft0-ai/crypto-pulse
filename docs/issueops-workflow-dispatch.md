# Reusable IssueOps workflow dispatcher

This document describes the source-controlled implementation of issue #356. The dispatcher is a repository control plane for converting one exact, reviewed issue comment into one exact `workflow_dispatch` request. It is not an execution authority by itself and it never receives model/provider secrets.

## Permanent boundary

The listener is `.github/workflows/issueops-workflow-dispatch.yml`. It reacts only to newly created issue comments. The default registry is `.github/issueops-workflow-dispatch.yml` and contains no active authorisation after the dispatcher implementation is installed.

An executable authorisation is a separately reviewed schema-v2 record. It freezes the governing issue and command, immutable owner identity, target workflow numeric ID/path/hash, fixed inputs, one-attempt limit, validity window, execution-tag ruleset identity, dispatcher workflow hash, and the `dispatch_attestation_v1` predicate type.

Comment text cannot choose a workflow, ref, input, model, provider or budget.

## One-time consumption

For authorisation `<id>` at the created-event source commit `<S>`, the runtime derives:

```text
issueops/dispatch/<id>--sha-<S>
refs/tags/issueops/dispatch/<id>--sha-<S>
```

The tag is a lightweight reference directly to `<S>`. The side-effect job checks the target workflow and runtime-observable execution-tag ruleset, rejects a pre-existing tag, then re-fetches and revalidates the exact triggering comment at the last possible point before tag creation.

Exactly one `POST /git/refs` is available in dispatcher code. Only an HTTP `201` response followed by exact ref read-back owns continuation. A timeout, reset, non-`201`, conflicting/pre-existing tag, or ambiguous result fails closed. The dispatcher never retries tag creation and never restores authority after the tag exists.

The separately provisioned tag ruleset is expected to be active for the IssueOps tag namespace, restrict update and deletion, and leave creation unrestricted in v1. Full bypass-actor review belongs to the separately governed provisioning stage because runtime read credentials do not reliably expose that protected field.

## Dispatch and run binding

After consumption, exactly one Actions write endpoint is available:

```text
POST /actions/workflows/{frozen_numeric_id}/dispatches
```

The ref is the derived execution tag and inputs are the frozen source-controlled map. The runtime requires the API `2026-03-10` direct HTTP `200` response containing the target workflow run identity. It does not infer a run from timestamps, actor, ref or search results and it never retries an uncertain dispatch.

The returned run is read back and must be attempt 1 of the frozen workflow, event `workflow_dispatch`, at the exact execution tag and source SHA.

## Signed receipt

A separate job in the same canonical dispatcher workflow revalidates the exact target run and creates a deterministic JSON subject plus a deterministic custom predicate. Both are compact, key-sorted UTF-8 JSON with one trailing LF.

The signed subject binds repository and owner identity, authorisation identity/hash/source SHA, triggering issue/comment/body hash, owner account identity, execution ref, dispatcher workflow/run identity and exact target workflow/run/ref/SHA.

The predicate repeats those cross-checkable values and adds the exact target event and frozen-input hash. Predicate values are claims, not signer identity.

The workflow signs the subject with `actions/attest` pinned to the immutable commit:

```text
1e69f48acb82d1966a394da916b4c1698aa569d6
```

The signing job has read-only Actions/contents/issues access plus only the OIDC and attestation writes needed to create the receipt. It has no `actions: write`, no `contents: write`, no protected environment and no provider secret.

## Reruns

Every dispatcher side-effect and signing boundary requires `github.run_attempt == 1` and the canonical dispatcher workflow/source SHA. A workflow or job rerun therefore cannot create another execution tag, issue a second target dispatch or sign a new receipt.

A later edit or deletion of the command after successful tag consumption does not restore, revoke or duplicate the consumed authority.

## Target-side verification is separately governed

This implementation does not modify `.github/workflows/governed-gpt-oss-quality-comparison.yml`, repository rulesets, the `governed-llm-dry-run` environment, or any Phase 9 authorisation.

Before a protected target can use this dispatcher, a separate reviewed stage must provision and review the immutable tag ruleset and environment tag policy, harden the target with its attempt-1 provenance gate, install the pinned `gh` v2.97.0 verifier contract from issue #356, add one reviewed authorisation record and only then create an authorised command.

A direct manual/API dispatch of a future protected execution tag must fail the target provenance gate unless the exact dispatcher-signed target-run receipt independently verifies.

## Implementation invariants

The deterministic tests enforce the source-controlled schema and owner binding; PR-comment, partial-command, disabled/expired, duplicate and rerun rejection; exact tag derivation; edit rejection before consumption; tag replay/race failure; ruleset update/deletion requirements; target workflow hash and run identity; no inferential dispatch correlation; deterministic receipt serialisation; immutable attestation-action pinning; minimal job permissions; and absence of provider secrets or protected environments.

Tests use fake transport only. They do not create a real tag, dispatch a workflow, write an attestation or call a provider.
