# Phase 14 — Deterministic site publication

Status: promoted for delivery planning; implementation not yet authorised by this roadmap record.

This roadmap spec promotes the accepted `deterministic-site-publication/v3` design from #455 as the next bounded CryptoPulse successor direction after Phase 13. It restores recent deterministic report publication without changing `main` as the sole publication authority or widening the product into Phase 13 temporal public rendering.

## Governance

```text
Shaping issue: #455
Accepted design: #455 comment 5307427797
Contract: deterministic-site-publication/v3
Fresh substantive design approval: #455 comment 5307453436
Owner successor/promotion authority: #455 comment 5307463217
Roadmap-promotion issue: #456
Trusted promotion baseline: 85f16d388c12669a0560844785f34bc68a67f033
```

## Problem statement

Scheduled source ingestion continues to produce validated repository-owned snapshots, but the public Pages site is not refreshed by that evidence path. The current chain stops before publication authority: rolling snapshot evidence does not automatically become an immutable deterministic report candidate on `main`, and Pages rebuilds only after relevant `main` changes.

A safe successor must restore normal deterministic freshness without trusting mutable rolling-branch state, letting ordinary writers substitute publication bytes, weakening trusted `main`, introducing a direct deployment path, or reintroducing a model/provider dependency.

## Goal

Deliver and prove a narrowly bounded deterministic publication path that:

- keeps `main` as the sole publication source of truth;
- derives one immutable two-file publication candidate from one exact trusted ingestion/generation identity;
- binds that exact App-created candidate head to a successful trusted default-branch generation run through immutable attestation;
- requires exact-head credential-free PR validation;
- refuses stale-base merges atomically through strict classic branch protection;
- uses one repository-scoped publication App only after separately authorised provisioning;
- merges through a metadata-only gate that executes no PR code;
- leaves the existing Pages and live-verification workflows as the deployment path;
- remains fail-closed, idempotent and initially inert.

## Frozen publication contract

```text
deterministic-site-publication/v3
```

The contract preserves these core boundaries:

```text
publication authority: main only
automatic candidate scope: exactly one snapshot JSON + one deterministic Markdown report
automatic eligibility: valid-ok only; no warning/error/blocking issue
idempotency: at most one accepted publication per canonical observation hour
candidate mutation: no rebase, update, regeneration, force-push retry or changed-head retry
fallback: none
activation states: disabled | pilot | recurring
initial activation: disabled
```

## Target publication flow

```text
scheduled trusted ingestion/generation on default branch
  -> pin exact main_base_sha and immutable snapshot identity
  -> require valid-ok deterministic eligibility
  -> generate exact deterministic report
  -> create one per-run/per-hour publication branch from main_base_sha
  -> push/open PR as dedicated repository-scoped publication App
  -> upload immutable trusted-generation attestation for exact run/attempt/head
  -> credential-free Validate CryptoPulse PR on exact candidate head
  -> default-branch metadata-only gate reconstructs attestation and candidate bytes
  -> require current main == attested main_base_sha
  -> enter protected publication environment only after all read-only guards pass
  -> mint short-lived repository-scoped App token
  -> attempt SHA-bound PR merge
  -> strict classic main protection requires candidate to remain up to date
  -> successful main push triggers existing Publish CryptoPulse Pages
  -> existing Verify CryptoPulse Live Pages verifies deployed commit/live identity
```

No candidate code is executed by the privileged merge gate.

## Trusted-generation attestation

The trusted default-branch generation run must upload one immutable Actions artefact after the App-created PR exists. Its run/attempt identity is encoded independently of editable PR prose and binds at minimum:

```text
publication_contract
generation_workflow_id
generation_workflow_run_id
generation_workflow_run_attempt
generation_workflow_head_sha
main_base_sha
observation_hour_utc
snapshot_commit_sha
snapshot_path
snapshot_sha256
report_path
report_sha256
candidate_branch
candidate_head_sha
pull_request_number
publication_app_actor_id
publication_app_slug
```

Required invariants include `generation_workflow_head_sha == main_base_sha`, expected repository-owned default-branch workflow identity, exactly one expected attestation artefact for the run/attempt, and exact reconstruction of current PR branch/head, App actor and candidate bytes.

Deletion, expiry, ambiguity, duplicate expected artefacts, changed head, changed bytes or inability to reconstruct evidence fails closed. PR prose is reviewer-visible evidence, not the security root.

## Publication App boundary

Provisioning is a later separately authorised gate. The intended App is installed only on `8ft0-ai/crypto-pulse` with exactly:

```text
Metadata:      read
Contents:      read/write
Pull requests: read/write
```

No Actions, Administration, Checks, Issues, Workflows, Secrets, Environments or Deployments write permission is part of the accepted boundary.

The App private key belongs only in a dedicated protected environment restricted to trusted `main`; PR refs are ineligible. Installation tokens are short-lived and repository-scoped. PR validation receives no App private key or installation token.

## Trusted-main controls

The existing active ruleset `20795849` remains the administrator-only trusted-main update boundary. Separately authorised provisioning may add exactly one publication-App integration with:

```text
bypass_mode: pull_request
```

The App must not receive `always` bypass and cannot directly push to `main`.

The existing classic `main` protection must separately require the actual PR-validation check context:

```text
Build site and check generated output
```

bound to the expected GitHub Actions check source with strict/up-to-date semantics enabled. This is the atomic stale-base interlock: if `main` advances after candidate creation, validation or the gate's last metadata read, the candidate is no longer up to date and GitHub refuses the merge.

The gate must also pass the exact current candidate head SHA to the merge operation. Head movement and base movement therefore both fail closed.

## Metadata-only merge gate

The default-branch gate may act only after successful `Validate CryptoPulse PR` completion. Before entering the protected environment or minting the App token it must prove, using read-only metadata/APIs, at least:

```text
validation conclusion == success
validated head SHA == current PR head SHA
PR is open, non-draft, same-repository and App-authored
base == main
candidate branch encodes one exact trusted generation run/attempt
generation run exists, succeeded and used the expected default-branch workflow
immutable attestation exists exactly once and reconstructs run/base/PR/App/head identity
snapshot/report paths and SHA-256 values reconstruct from exact candidate bytes
changed files == exactly one snapshot JSON + one report Markdown
snapshot quality == valid-ok
no warning/error/blocking issue
canonical observation hour
no accepted publication already exists for that hour
no blocking review, unresolved thread or failed/pending required check
current main SHA == attested main_base_sha
activation state authorises this exact merge mode
```

The gate reads exact candidate bytes through GitHub object/content APIs at the pinned candidate SHA. It does not check out the candidate or execute its scripts.

## Pages and live verification

No direct deployment is added to ingestion, generation or the merge gate.

The existing `.github/workflows/pages.yml` remains the sole Pages deployer from `main`, building disposable `_site/` output after the publication merge. `Verify CryptoPulse Live Pages` remains the post-deployment verifier.

The bounded live pilot, if separately authorised later, must prove both the expected `main` merge commit and that the live latest report resolves to the newly merged deterministic report. A verification failure records failure only; it does not trigger rollback, fallback or another automatic merge.

## Delivery sequence and authority gates

The accepted design requires this order:

1. roadmap promotion and delivery planning;
2. credential-free implementation and negative-corpus proof with activation `disabled`;
3. genuinely fresh substantive exact-candidate implementation review;
4. separate owner provisioning authority;
5. provisioning readback proof for exact App scope/permissions, protected environment, exact ruleset bypass, exact required-check source and `strict=true`;
6. non-merging App integration proof while still `disabled`;
7. explicit stale-base race proof showing a concurrent `main` advance refuses merge without candidate update;
8. separate owner live-pilot authority for one exact candidate under `pilot`;
9. fresh pilot adjudication proving merge -> existing Pages -> live identity;
10. separate owner recurring-activation authority before `recurring`.

No earlier gate grants authority for a later one.

## Acceptance gates

- [ ] Roadmap promotion lands as planning-only state with all v3 trust/product boundaries preserved.
- [ ] A delivery-control issue freezes the exact implementation slices and credential-free proof matrix before implementation begins.
- [ ] Implementation lands with activation `disabled` and cannot become operational merely by merge.
- [ ] Trusted-generation attestation reconstruction proves exact run/attempt/base/PR/App/head/byte identity and fails closed after ordinary-writer head mutation.
- [ ] PR validation remains credential-free and succeeds only for the exact current candidate head.
- [ ] Metadata-only gate executes no PR code and rejects every identity/scope/quality/duplicate/check/base/head/activation mismatch.
- [ ] Strict classic `main` protection and exact required-check source are proved by provisioning readback before operational use.
- [ ] Stale-base race proof demonstrates that a concurrent `main` advance prevents automatic merge without rebase/update/regeneration.
- [ ] Dedicated App remains repository-scoped and permission-minimal with only PR-only ruleset bypass.
- [ ] At most one `valid-ok` publication is accepted per canonical observation hour; there is no stale-hour fallback.
- [ ] Existing Pages/live-verification chain remains the sole deployment path and `_site/` remains generated-only.
- [ ] Live pilot and recurring activation occur only after their separate owner gates and accepted evidence.
- [ ] No model/provider, Phase 13 temporal public rendering, forecasting, sentiment, advice or broader product scope is introduced.

## Non-goals

Phase 14 does not authorise or deliver:

- public rendering of Phase 11/13 temporal series or charts;
- changes to frozen Phase 10/11/12/13 evidence contracts;
- model/provider invocation, selection, credentials or scheduled LLM generation;
- forecasting, causal claims, sentiment/risk taxonomy, technical levels, targets, watchlists or trading guidance;
- committed `_site/` output;
- deployment from the rolling branch or a publication candidate branch;
- direct publication-App push to `main`;
- broad repository automation credentials;
- automatic publication of degraded/warning/error evidence;
- rebase, stale-hour fallback, changed-head retry or hidden candidate regeneration.

## Risks and mitigations

### Risk: ordinary writers modify an App-authored publication branch

Mitigation: the immutable trusted-generation attestation binds the exact trusted generation run/attempt and exact candidate head/bytes; any changed head or byte identity fails closed.

### Risk: `main` advances between the gate's last read and merge

Mitigation: strict classic required-check protection requires the candidate branch to remain up to date at merge evaluation; a concurrent `main` advance makes the merge ineligible.

### Risk: the new App becomes a general bypass principal

Mitigation: one repository installation, minimal permissions, protected credential environment, short-lived token, and only PR-mode bypass on ruleset `20795849`.

### Risk: publication automation silently widens product scope

Mitigation: automatic candidates are exactly one snapshot plus one existing deterministic Markdown report; Pages remains unchanged and Phase 13 temporal public rendering stays parked.

## Definition of done

Phase 14 is complete only when the accepted v3 publication contract is implemented and independently reviewed, provisioning and stale-base controls are separately authorised and proved, one bounded live pilot is accepted end to end through the existing Pages/live-verification path, recurring activation is separately authorised, deterministic recent publication operates under the closed valid-ok/idempotent contract, close-out evidence is recorded, and generated `_site/` output remains uncommitted.
