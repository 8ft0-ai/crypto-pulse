# Phase 14 — Deterministic site publication

Status: complete at the safe inert control-plane boundary; operational activation deferred.

Primary outcome: CryptoPulse now contains the reviewed `deterministic-site-publication/v3` control plane, dedicated publication-App/protection boundary, and candidate-identity proof machinery needed for a future deterministic publication rollout, while leaving automatic publication disabled and explicitly deferring the unresolved live stale-base race, live pilot, and recurring activation.

## Governance

```text
Shaping issue: #455
Accepted design: #455 comment 5307427797
Contract: deterministic-site-publication/v3
Fresh substantive design approval: #455 comment 5307453436
Owner successor/promotion authority: #455 comment 5307463217
Roadmap promotion: #456 / PR #457
Parent delivery-control issue: #458
Inert implementation issue: #459
App/protection provisioning issue: #461
App integration proof carrier: #462
Candidate attestation/head-change proof: #465
Stale-base live race proof: #472 — closed not planned / deferred
Cadence restoration issue: #473
Deferred live-proof successor: #477
Owner inert-boundary close-out decision: #458 comment 5361248316
Close-out file freeze: #458 comment 5361279207
```

The owner deliberately closed Phase 14 at the safe inert boundary after the live stale-base race remained scheduler-timing dependent through the consumed V1–V13 proof-runner series. This record does not reinterpret that deferred live proof as successful.

## Delivered control plane

PR #460 merged the inert `deterministic-site-publication/v3` implementation at merge commit `02f9ef75633a8bff4f84448d24e0f6167c610b73` after exact-head validation run `31978089661` succeeded.

The delivered implementation establishes:

- immutable publication intent from trusted ingestion evidence;
- exact trusted `main` / source-run binding;
- deterministic report generation with no model/provider dependency;
- exact two-file candidate scope: one snapshot JSON plus one deterministic Markdown report;
- immutable trusted-generation attestation binding source/generation run, attempt, base, PR, App, branch, head, snapshot and report identity;
- credential-free exact-head PR validation;
- a default-branch metadata-only gate that executes no candidate code and reconstructs candidate/attestation identity from pinned bytes;
- explicit `disabled | pilot | recurring` activation semantics with missing/invalid activation failing closed;
- stale-current-main and changed-head rejection logic in the policy/helper corpus;
- no candidate rebase, update, regeneration, force-push retry or stale-hour fallback.

The implementation landed inert. Merge of the implementation alone did not make deterministic publication operational.

## Publication App and trusted-main boundary

The separately governed #461 provisioning gate established one repository-scoped publication GitHub App and the protected execution boundary required by the accepted design.

Sanitised readback and later proof established:

- publication App id `4618782` / slug `cryptopulse-deterministic-pub`;
- repository installation limited to `8ft0-ai/crypto-pulse`;
- repository permissions limited to Metadata read, Contents read/write and Pull requests read/write;
- protected environment `deterministic-publication-control` restricted to trusted `main`;
- strict classic `main` required status check `Build site and check generated output` bound to GitHub Actions app id `15368`;
- publication App ruleset bypass limited to `pull_request`, not `always`;
- activation remained absent/`disabled` throughout provisioning and non-merging integration proof.

PR #463 added the inert non-merging App integration proof carrier and merged at `7da93140599f7f5e97d2596aa6b068ed2b92bdeb`. The separately authorised integration proof run `31991433001`, attempt `1`, completed successfully and cleaned up its disposable App-authored PR/branch without merge.

## Candidate identity and changed-head proof

Issue #465 closed successfully after the trusted generation proof mode and its bounded remediation were reviewed and merged.

Key implementation history:

```text
PR #466 — add Phase 14 candidate attestation proof mode
merge: 7da82b8eba396a8c4c00be5e7b1af63a9c5c256b

PR #467 — fix unpublished-hour check ordering after the first consumed proof exposed a proofability defect
merge: a965541af00aea4c7305569f761d6e054155228f

Final proof adjudication: #465 comment 5327452648
status: proof-success-cleanup-complete
```

The accepted proof established the candidate-specific security properties that the immutable attestation reconstructs the exact App-created candidate head/bytes and that an ordinary-writer head change after trusted generation is rejected before the privileged merge boundary. The disposable proof PR was closed unmerged and its branch deleted.

## Stale-base live race — explicitly deferred

Issue #472 attempted to prove the remaining live production stale-base race using the real scheduled ingestion -> trusted generation -> candidate validation -> metadata gate/protection path.

The repository already contains credential-free stale-current-main rejection coverage and strict required-check protection. The remaining challenge was to observe the real production race deterministically without weakening those controls.

Owner-local orchestration versions V1–V13 were bounded one-attempt runners. The final V13 attempt was consumed and stopped fail-closed:

```text
STOP — first qualifying V13 source was already completed before pilot-id binding; restore state and stop with no later source
```

V13 authority was #472 comment `5353902657`; its runner SHA-256 was `8d41df01ed452fa5311a279e3088492f66b9c7870add2de935077a08a3a24177`. The runner restored its temporary publication-variable state before terminal STOP.

The V-series demonstrated fail-closed behaviour under missed/ambiguous scheduler timing, but it did **not** produce the required live sequence of one valid production candidate, a subsequent `main` advance, and observed stale-base merge refusal. That criterion is therefore not claimed as proven.

Issue #472 was closed `not planned` / deferred. Any future deterministic live stale-base proof belongs to #477. V1–V13 must not be revived and another timing-only V14+ runner is explicitly out of scope.

## Cadence and final repository state

The temporary Phase 14 15-minute ingestion cadence was removed during close-out. Reviewed PR #476 restored the normal hourly `17 * * * *` cadence and merged at current close-out baseline:

```text
main: bf729ff61731ce515e48c9cd45ab7c1aa3266a5e
```

The rolling source snapshot PR remains the normal ingestion evidence surface. Generated `_site/` output remains uncommitted.

No Phase 14 close-out action enables a model/provider path, Phase 13 temporal public rendering, forecasting, sentiment, advice, or broader product scope.

## What Phase 14 proves

At close-out, Phase 14 has accepted evidence for:

- reviewed inert v3 implementation and credential-free negative-corpus proof;
- trusted intent/candidate/attestation identity boundaries;
- exact-head validation and changed-head rejection;
- dedicated repository-scoped App integration;
- protected-environment and strict trusted-main interlocks;
- fail-closed disabled activation;
- fail-closed behaviour during unsuccessful live race orchestration;
- restoration to the normal hourly ingestion cadence.

It does **not** claim:

- a successful real live stale-base race proof;
- a successful live publication pilot;
- end-to-end live Pages identity proof for a Phase 14 publication candidate;
- `recurring` activation;
- ongoing automatic deterministic publication in production.

## Delivery graph disposition

`planning/delivery/delivery.yaml` and generated `planning/delivery/graph.md` remain unchanged under the compact graph rules.

Phase 14 closes with publication activation disabled and therefore does not add a newly operational live publication stage to the causal delivery pipeline. The enduring residual boundary is more accurately represented by this delivery record plus backlog issue #477 than by adding an operational graph edge that would imply live publication was delivered.

## Carry-forward

Phase 14 is complete at the safe inert boundary.

If deterministic automatic publication later becomes valuable enough to operationalise, begin from #477 rather than reopening the consumed V-series. A future programme must first establish a deterministic live stale-base proof carrier, then separately govern one bounded live pilot, Pages/live identity adjudication, and any later `recurring` activation.

Until then, publication activation remains absent/`disabled`, no active successor phase is selected by this close-out, and the repository retains the reviewed control plane as dormant infrastructure rather than an operational publishing service.
