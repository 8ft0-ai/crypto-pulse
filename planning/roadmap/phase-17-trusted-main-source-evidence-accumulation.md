# Phase 17 — Trusted-main source-evidence accumulation and freshness

Status: complete.

This roadmap spec records the intended `trusted-main-source-evidence-accumulation/v1.1` boundary promoted from #516 and the final delivered disposition. Completed implementation/proof evidence is recorded in `planning/delivery/phase-17-trusted-main-source-evidence-accumulation.md` and the canonical GitHub history.

## Problem statement

Phase 16 made sparse repository evidence truthful and reader-safe, but it deliberately left #497 T2 source-evidence accumulation outside scope. The hourly ingestion workflow can already produce and validate one canonical Phase-12 source snapshot per scheduled run, yet its mutable rolling branch is not trusted evidence authority and unmerged candidates are not retained as a useful adjacent population on protected `main`.

The remaining problem was therefore not reader presentation and not automatic publication. It was how to accumulate exact already-generated, already-validated source evidence into bounded, reviewable source-only candidates so protected `main` could gain enough adjacent observations for the frozen Phase 13 / 15 / 16 temporal consumers to become useful without weakening repository authority.

## Goal

Deliver the minimum safe accumulation and promotion capability defined by `trusted-main-source-evidence-accumulation/v1.1`:

- immutable scheduled-ingestion artifacts are the only promotable input provenance envelope;
- exact snapshot bytes that validate under `phase12-observation-hour/v1` are the only authority for canonical observation-hour identity;
- one deterministic manifest classifies a bounded `H_main + 1 ... H_main + 25` window;
- unsafe evidence fails closed by default;
- terminal recovery is an explicit owner decision, exact and durable, never promotes excluded bytes, never elects a duplicate winner and never synthesises a missing hour;
- a source-only candidate may reach protected `main` only through exact-head validation, fresh substantive review and a separate owner merge decision;
- protected `main` remains the sole public evidence authority.

## Non-goals

Phase 17 does not authorise or introduce:

- automatic merge;
- recurring accumulation-candidate scheduling before the separate Slice E decision;
- Phase 14 `pilot` or `recurring` publication activation;
- #477 promotion or publication-App merge authority;
- mutable rolling/candidate branches as public evidence authority;
- interpolation, smoothing, carry-forward, invented values, synthetic cursor movement or historical backfill;
- a new source provider, model, LLM, report-generation path or credential requirement;
- Markdown report generation authority;
- forecast, recommendation, signal, technical-level or personalised guidance;
- reinterpretation of the frozen Phase 12 / 13 / 15 / 16 contracts;
- Pages authority redesign or committed generated `_site/` output;
- deletion, rewrite or rename of already-promoted trusted source snapshots.

## Target authority chain

```text
scheduled ingestion run
  -> immutable ingestion artifact + exact snapshot bytes
  -> deterministic trusted-main accumulation manifest
  -> source-only candidate branch / PR
  -> exact-head validation + fresh substantive review
  -> separate owner merge decision
  -> protected main
  -> unchanged Phase 13 comparison / series
  -> unchanged Phase 15 / 16 public reader surfaces
```

No model, report generator, deterministic-site-publication candidate, Phase 14 App or mutable rolling branch enters this authority chain.

## Immutable input authority

Production accumulation inputs are only successful scheduled executions of `.github/workflows/ingest-crypto-sources.yml` (`event == schedule`) whose immutable artifact contains:

```text
deterministic-publication-intent-<run_id>-<run_attempt>/
  deterministic-publication-intent.json
  payload/snapshot.json
```

For each candidate input, the accumulator binds repository, workflow, event, run ID, run attempt, artifact identity, snapshot SHA-256, recorded snapshot commit/blob/path and current-main validator compatibility. Producer-time success is provenance evidence; current-main revalidation is the promotion compatibility gate.

Only exact snapshot bytes that pass the frozen Phase-12 observation-hour validator establish canonical hour identity. Cron slots, scheduled timestamps, workflow timestamps, artifact upload time, commit/file timestamps, another run attempt or expected cadence are never used to invent an hour.

For reruns of one run ID, only the highest successful attempt is eligible. Distinct successful run IDs resolving to the same actual canonical hour remain duplicate evidence and are never automatically ranked or elected.

Operational run diagnostics may explain that executions failed, were cancelled, timed out or were delayed, but diagnostics do not establish a Phase-12 hour and cannot create source evidence.

## Deterministic candidate window and manifest

Contract identity:

```text
trusted-main-source-evidence-accumulation/v1.1
```

Let `H_main` be the maximum canonical Phase-12-participating observation hour already present on the exact protected-main candidate base under the existing Phase 13 participation semantics.

The bounded target window is:

```text
H_main + 1 hour ... H_main + 25 hours
```

inclusive, therefore at most 25 canonical hours per candidate.

The canonical manifest binds at least the exact base SHA/tree, anchor hour, window bounds, ordered hour records, input identities, per-hour classifications, added source paths/hashes, blocking findings, exact recovery-decision identities where applicable and a deterministic `candidate_id` derived from canonical manifest bytes. Wall-clock build time is not part of `candidate_id`.

Normal hour dispositions are:

- `eligible`;
- `no-promotable-observation`;
- `duplicate`;
- `path-conflict`;
- `already-trusted`;
- `terminal-excluded`.

Unsafe evidence whose canonical hour cannot be established remains an input-level blocker rather than being assigned an inferred hour.

## Recovery and fail-closed semantics

Unsafe evidence blocks the candidate by default. A terminal exclusion can be applied only through an explicit owner decision recorded as the separately defined durable recovery record:

```text
trusted-main-source-evidence-recovery-decision/v1
```

The owner decision record is a top-level GitHub issue comment on the active Phase 17 delivery-control issue or an explicitly linked recovery issue. It is supplied explicitly to a manual recovery invocation; the accumulator does not discover or choose recovery authority automatically.

The manifest binds the exact recovery comment ID, body hash, blocker fingerprint, strongest immutable input identities and canonical hour when one is provable. Edited, mismatched or stale recovery decisions are invalid. The exact input is reclassified against current protected `main` before recovery is applied.

Recovery can exclude unsafe bytes so later valid hours in the same bounded window may proceed, but it never:

- makes invalid evidence valid;
- promotes excluded bytes;
- creates a source snapshot;
- elects one member of a duplicate set;
- infers a missing canonical hour;
- reconstructs unavailable evidence from logs, PR text or screenshots;
- rewrites trusted-main evidence;
- advances `H_main` synthetically.

Duplicate recovery excludes the whole conflicting set. Unavailable/unverifiable input may be terminally excluded with canonical hour `null` when the hour cannot be proved. A path-conflict recovery binds both staged and trusted-main identities and never rewrites trusted main.

If recovery leaves no eligible additions, no merge occurs merely to move a cursor. `H_main` advances only when real validated source evidence is merged to protected `main`.

## Candidate branch and review boundary

A candidate refresh always starts from exact current protected `main`, rebuilds the complete manifest from immutable inputs and creates/resets a disposable source-only candidate branch. The candidate may add only exact eligible files under `data/crypto/hourly/...`; it may not modify, rename or delete historical source evidence or touch non-source paths.

Any base/head/candidate change invalidates previous substantive review. A candidate is merge-eligible only after:

- exact base freshness is proved;
- additions-only source diff is proved;
- every added file matches the canonical manifest;
- current source and observation-hour validators pass;
- independent deterministic replay yields the same `candidate_id` and file set;
- required repository validation passes for the exact head;
- a genuinely fresh substantive review records `APPROVED` for that exact head/candidate identity;
- a separate owner merge decision is recorded after the approval;
- merge uses an exact expected-head guard.

No phase-level approval, old candidate review or recurring-schedule authority substitutes for the candidate-specific merge decision.

## Freshness and retention

Phase 17 changes evidence availability, not the public definition of `current` or `live`. Operational manifests may state exact observation hours and bounded counts, but Phase 16 public surfaces continue to derive claims only from exact checked-out trusted-main evidence and use the existing safe repository-recency language.

Promoted source evidence is append-only under v1.1. The phase does not delete, rewrite or rename trusted source snapshots. Existing ingestion-artifact retention remains unchanged; if exact artifact bytes are unavailable, the accumulator fails closed unless an exact terminal recovery decision excludes that input without fabricating evidence.

## Compatibility boundaries

Phase 17 may increase the trusted evidence population but must not reinterpret:

- `phase12-observation-hour/v1`;
- Phase 13 adjacency, comparison, series, duplicate/missing/invalid and gap semantics;
- `phase15-public-temporal-evidence/v1`, including `metric / BTC.price_usd / 24 slots` identity;
- Phase 16 reader authority, chronology, provenance and safe recency wording.

Phase 14 remains complete and inert at its existing control-plane boundary. #477 remains parked. Reuse of the immutable ingestion publication-intent artifact is source provenance reuse only and imports no Phase 14 publication authority.

## Acceptance gates

Phase 17 is complete because all of the following have been proved under separate governed candidates where required:

- [x] Slice A implements deterministic v1.1 accumulation/recovery logic and closed offline fixtures with stable repeat materialisation.
- [x] Exact input/run/attempt/artifact/snapshot binding and current-main compatibility validation are proved.
- [x] Failure-before-artifact, delayed-success, rerun-hour drift and same-hour distinct-run duplicate cases preserve snapshot-only hour authority.
- [x] Permanent invalid, duplicate, unavailable and path-conflict cases fail closed without recovery and permit later valid evidence only after an exact terminal exclusion.
- [x] Recovery drift is rejected and no synthetic cursor movement is possible.
- [x] Slice B first delivered a `workflow_dispatch`-only source candidate builder with explicit recovery-comment-ID input, no schedule and no merge capability.
- [x] Candidate construction is additions-only under `data/crypto/hourly/...`, deterministic from current main and invalidates review on refresh.
- [x] Slice C completes one separately authorised real candidate pilot of no more than 25 canonical hours through exact-head validation, fresh review and separate owner merge authority.
- [x] Slice D proves the exact merged source population through the unchanged Phase 13 / 15 / 16 consumer chain and existing Pages deployment path.
- [x] No Phase 14/#477 activation, model/provider work, report-generation authority or public `live/current/up to date` claim is introduced.
- [x] Slice E presents and records a separate owner decision on recurring candidate refresh; the selected daily candidate refresh is separately implemented and merged without automatic merge capability.
- [x] Close-out records exact implementation, validation, merged identities and preserved boundaries in `planning/delivery/` and the delivery ledger/graph metadata where applicable.

## Delivery sequence

### Slice A — deterministic accumulation contract and offline proof

Implemented the pure deterministic manifest/selection/recovery logic and closed fixtures with no GitHub write path.

### Slice B — manual source-only candidate builder

Delivered the manual builder that gathers immutable scheduled-ingestion inputs, invokes Slice A, emits the canonical manifest/artifact and opens or refreshes the disposable source-only candidate PR. Recovery comment IDs remain explicit manual inputs and the workflow has no merge capability.

### Slice C — bounded real promotion pilot

The first separately authorised dispatch failed before canonical candidate evidence and its one-dispatch authority was consumed. After separately governed remediation, a fresh pilot produced PR #535. The reviewed candidate promoted 17 canonical hours with zero remaining blockers and merged to protected main as `877670ac6739fcfda1614c407a90c7417b1c7320` under a separate owner decision and expected-head guard.

### Slice D — consumer and public proof

The unchanged Phase 13 / 15 / 16 chain was replayed/proved from the promoted state. Pages run `33333144803` and live runs `33333182395` / `33333262565` proved the existing public path without changing renderer semantics to manufacture fuller evidence.

### Slice E — recurring refresh decision

The separate owner decision selected **daily candidate refresh only**. PR #539 merged the exact `47 0 * * *` UTC schedule as `948ba28b965d9c3c9e5760af89f7367503f2a84f`. Manual `workflow_dispatch` remains available. Scheduled runs bind exact event `github.sha`, require live protected main to match, and receive no recovery-comment authority. Every candidate merge remains separately governed.

## Delivered close-out disposition

```text
Slice A: COMPLETE
Slice B: COMPLETE
Slice C: PASS — bounded real source-evidence promotion complete
Slice D: PASS — unchanged consumer/public proof complete
Slice E: DAILY_CANDIDATE_REFRESH — merged/configured on protected main
Protected main before close-out record: 948ba28b965d9c3c9e5760af89f7367503f2a84f
Phase 14/#477 activation: no
Automatic candidate/source merge: no
Successor phase selected: no
```

The completed management record lives at `planning/delivery/phase-17-trusted-main-source-evidence-accumulation.md`. The delivery ledger and compact graph record only the representative causal evidence; the full issue/PR/run/recovery trail remains canonical in GitHub.

## Risks and mitigations

### Risk: staging becomes de facto evidence authority

Mitigation: candidate branches are disposable and never consumed by public readers; only protected-main merges make source bytes authoritative.

### Risk: scheduler or workflow metadata invents temporal identity

Mitigation: exact Phase-12-valid snapshot bytes are the sole authority for canonical observation hour; failed/delayed/rerun diagnostics remain separate.

### Risk: a permanent unsafe input wedges all later valid evidence

Mitigation: explicit terminal recovery can exclude the exact unsafe input while preserving its blocker identity and leaving the missing evidence truthful. Exclusion never promotes the bytes or advances the trusted cursor by itself.

### Risk: recovery becomes an automatic skip mechanism

Mitigation: recovery is durable owner control-plane input supplied explicitly to manual invocation, bound byte-for-byte into candidate identity, revalidated against current main and incapable of choosing a duplicate winner.

### Risk: automation silently expands into publication authority

Mitigation: daily automation is limited to candidate refresh, has no merge capability, leaves Phase 14/#477 inert and does not substitute for candidate-specific review/owner merge authority.

## Definition of done

The phase is complete when:

- [x] the Phase 17 parent delivery-control issue and linked slice/proof work are durable;
- [x] all required implementation candidates receive exact-head validation and fresh substantive review;
- [x] any source-evidence merge uses separate owner authority and exact-head guards;
- [x] one bounded real promotion and unchanged-consumer/public proof are complete;
- [x] the recurring refresh decision is separately recorded and its selected daily candidate-refresh implementation is separately validated/reviewed/merged;
- [x] the completed Phase 17 delivery record is added under `planning/delivery/`;
- [x] `planning/delivery-log.md` and delivery metadata/graph are updated where applicable;
- [x] roadmap/backlog state accurately records the completed phase and still-parked follow-on work;
- [x] generated `_site/` output is not committed.

## Governing evidence

- shaping issue: #516;
- exact approved design: #516 comment `5418718664` — `trusted-main-source-evidence-accumulation/v1.1`;
- fresh substantive approval: #516 comment `5425040365` — `APPROVED`;
- owner promotion/delivery authority: #516 comment `5425197783` — `ACCEPT`;
- roadmap promotion control: #521;
- roadmap promotion candidate: PR #522;
- parent delivery-control issue: #523;
- exact close-out plan: #523 comment `5471702402` — `phase17-close-out-plan/v1`;
- fresh close-out plan review: #523 comment `5471705380` — `APPROVED`.

The completed Phase 17 programme grants no Phase 14/#477 activation, model/provider/report-generation authority, automatic source-evidence merge or successor-phase authority.
