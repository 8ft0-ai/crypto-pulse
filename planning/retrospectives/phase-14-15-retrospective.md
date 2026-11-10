# Phase 14–15 delivery retrospective

Date: 2026-08-22

Status: retrospective record; no successor phase or improvement implementation is authorised by this document.

Governing issue: #493

## Scope

This retrospective covers the completed Phase 14 deterministic-site-publication programme and the completed Phase 15 public deterministic temporal-evidence programme. It evaluates delivery and proof practice rather than reopening either phase.

The primary evidence base is the repository's completed delivery records and the governed issues/PRs they identify, especially:

- `planning/delivery/phase-14-deterministic-site-publication.md`;
- `planning/delivery/phase-15-public-deterministic-temporal-evidence.md`;
- Phase 14 control issue #458 and deferred proof issue #477;
- Phase 15 shaping issue #479 and delivery-control issue #482;
- Phase 15 evidence prerequisite #484 / PR #485;
- validation-trigger remediation #486 / PR #487;
- trusted-main evidence promotion PR #488;
- Phase 15 site integration #489 / PR #490;
- Phase 15 close-out #491 / PR #492.

This record distinguishes completed facts from recommendations. Recommendations below are candidate improvements only and require separate shaping, review and authority before implementation.

## Executive assessment

The engineering outcome is stronger than the process efficiency.

Across Phases 14 and 15, CryptoPulse repeatedly preserved the most important control: do not claim a property that the evidence has not actually demonstrated. Phase 14 closed at a safe inert boundary instead of representing the unobserved live stale-base race as proven. Phase 15 then delivered one narrow public temporal-evidence surface without implicitly operationalising Phase 14, promoting a mutable rolling branch to public authority, adding model/provider behaviour, or drifting into forecast/advice semantics.

That evidence discipline should be retained.

The principal retrospective finding is that several expensive coordination loops were caused not by unsafe implementation behaviour but by weaknesses in the proof or delivery apparatus. Those weaknesses failed closed, which was correct, but some could have been discovered earlier or represented more mechanically.

## What worked well

### 1. Scope boundaries remained intact

Phase 15 had many plausible expansion paths: more metrics, richer cards, rolling-branch rendering, automatic publication, generated narrative, model/provider selection, or broader navigation. None leaked into the delivered `phase15-public-temporal-evidence/v1` boundary.

The final public scope remained exactly one historical `metric / BTC.price_usd` series over 24 canonical observation-hour slots, one generated `temporal.html` page and one low-prominence discovery link. Phase 14/#477 operationalisation, model/provider work, forecasting/advice and broader market-product scope remained separately parked.

This was successful scope governance rather than merely conservative implementation.

### 2. Evidence honesty was consistently fail-closed

Phase 14's V1–V13 orchestration attempts did not produce the required live production stale-base race observation. The programme correctly recorded that fact and closed at the safe inert control-plane boundary. The attempts are evidence of fail-closed behaviour under missed or ambiguous timing; they are not represented as evidence that the live acceptance criterion succeeded.

Phase 15 similarly distinguished GitHub's successful Pages deployment plus inspection of the exact deployed artefact from an independent second CDN HTTP fetch. The close-out did not claim a network observation that the close-out context had not performed.

This distinction between what is strongly inferred and what is directly observed is worth preserving as a project norm.

### 3. Immutable evidence promotion was well designed

Phase 15 could not truthfully build the public temporal page from the then-current trusted `main`, because it contained no Phase-13-participating observation-hour snapshot. The accepted design therefore required a separately governed prerequisite instead of using the mutable `automation/source-snapshot-rolling` branch as public authority or rewriting historical evidence.

Issue #484 froze one exact successful scheduled-ingestion snapshot, including its source run/job, source commit, blob identity, SHA-256, quality state and canonical observation hour. The eventual promotion PR #488 added those exact bytes to trusted `main` without modifying prior snapshots.

That is a strong example of repository-owned evidence promotion with immutable provenance.

### 4. Fresh substantive review provided real value

Fresh review was not merely ceremonial. It caught substantive design defects during Phase 15 shaping and required bounded correction before promotion. Later exact-candidate review preserved the distinction between implementation authorship and independent adjudication even in a single-maintainer repository.

The retrospective does not recommend weakening fresh substantive review, exact-head validation, immutable candidate identities or separately bounded owner authority for consequential actions.

## Where delivery cost more than necessary

### 1. Phase 14 iterated the proof apparatus too long

The Phase 14 live stale-base objective depended on observing a specific timing sequence involving ordinary scheduled ingestion, trusted candidate generation, a subsequent `main` advance and a stale-base refusal through the real production path.

V1–V13 were bounded and fail-closed, but they remained attempts to capture a scheduler-timing condition. By V13, the terminal result was still that the first qualifying scheduled source had completed before the required binding point. The programme eventually concluded that another timing-only V14+ runner would be the wrong response and deferred future work to #477, where a deterministic proof carrier could first be designed.

The lesson is not that V1–V13 were unsafe. The lesson is that repeated failures caused by the same uncontrollable proof mechanism should trigger proof redesign earlier.

A useful distinction for future programmes is:

- implementation failure: the system under test violates or cannot meet the intended contract;
- proof-apparatus failure: the system may be behaving correctly, but the current observation mechanism cannot deterministically demonstrate the required property.

Repeated instances of the second class should have a bounded attempt budget and a redesign gate.

### 2. Phase 15 did not preflight required-check trigger feasibility

The accepted Phase 15 plan required the trusted-main evidence candidate to receive full exact-head repository validation before fresh review and merge.

PR #485 was correctly created as an exact one-file snapshot candidate. However, `.github/workflows/pr-validation.yml` did not then include the source-snapshot path class in its `pull_request.paths` filter. As a result, the required `Build site and check generated output` context could not be produced for the exact candidate at all.

Issue #486 and PR #487 repaired the validation trigger with the minimum one-line semantic change, after which the source-evidence candidate had to be re-frozen/rebuilt against the new trusted base and ultimately merged as PR #488.

The repository failed closed, which was correct. The avoidable cost was discovering at candidate time that the planned file class could not exercise the required gate.

Future planning should include a gate-feasibility preflight: for every planned candidate file class, verify before freezing the implementation plan that all required checks are triggerable and that every promised post-merge proof has an executable evidence path.

### 3. Governance state is correct but expensive to reconstruct

The current workflow intentionally separates shaping, review, owner authority, roadmap promotion, delivery control, implementation planning, slice authority, exact-head validation, fresh review, merge authority, post-merge proof and close-out.

Those distinctions protect useful boundaries. The inefficiency is that the current state is primarily encoded across human-readable issue and PR comments. A later context often has to reconstruct a long chain of comment IDs, commit identities and gate dispositions before determining the next authorised action.

CryptoPulse already makes data, candidates and deployments increasingly deterministic and machine-verifiable. The same philosophy should be applied to delivery governance.

A future improvement could provide a small canonical machine-readable governed-state representation containing only decision-critical current identities and gate dispositions, while retaining comments and delivery records as explanatory/audit evidence. Such a representation must not replace fresh substantive reasoning or turn an old disposition into authority for a materially changed candidate.

### 4. Lifecycle completeness was not automatically checked

Phase 15 delivery-control issue #482 was correctly closed only after the close-out candidate merged and post-merge verification succeeded. However, shaping issue #479 remained open after the design had been accepted, promoted and fully delivered. It was closed later as housekeeping after an explicit repository-attention check.

No safety property was lost, but the state was misleading: an old shaping issue still appeared active after the governed programme had completed.

A future close-out check should enumerate shaping, promotion, child, remediation and delivery-control issues associated with the programme and require an explicit terminal disposition for each. The check should not blindly close issues; backlog/deferred work such as #477 must remain open when that is the intentional state.

### 5. Existing live Pages verification should be better integrated into close-out evidence

The repository already contains `.github/workflows/verify-live-pages.yml`. It is designed to run after successful `Publish CryptoPulse Pages`, uses Playwright/Chromium against the public Pages URL, publishes a verification summary and uploads live-site evidence.

The Phase 15 delivery record nevertheless correctly states that its close-out context could not independently perform a second CDN HTTP fetch, so its durable publication proof relied on GitHub's successful deployment state plus inspection of the exact deployed artefact.

The evidence currently reviewed here does not establish whether the automatic live-verification workflow failed to run, ran but was unsuitable for the Phase 15 identity check, or succeeded but was not incorporated into the close-out chain. That should be investigated before changing anything.

The process goal should be simple: when a Pages-affecting delivery has a valid automatic live-verification result for the exact deployed identity, close-out should consume it directly. If no valid result exists, the close-out record should explain why rather than silently substituting a weaker or different signal.

## Product-level lesson

Phase 15 is a strong architectural proof, but its purpose was intentionally narrower than a mature crypto-information product.

The programme proved that validated repository-owned Phase 13 evidence can cross the public-site boundary deterministically, transparently and with explicit gaps/provenance. It did not decide whether CryptoPulse should now optimise primarily for:

1. an engineering/governance demonstration that showcases deterministic evidence, governed automation and reproducible delivery; or
2. a genuinely useful public crypto-information experience built on those deterministic foundations.

Those directions overlap, but they are not the same roadmap. The first tends to prioritise stronger controls and proof surfaces; the second requires explicit user/product decisions about data breadth, freshness, presentation and usefulness while preserving the demo/non-advice boundary.

No successor is selected by this retrospective. A future shaping decision should address product direction before defaulting to another infrastructure phase simply because infrastructure work is easier to specify deterministically.

## Candidate carry-forward improvements

The following are retrospective recommendations, not authorised work.

### A. Gate-feasibility preflight

Before freezing an implementation plan, verify that every proposed candidate file class can trigger every required validation/check context and that each required post-merge proof has an executable evidence path.

### B. Proof-attempt budget and redesign gate

When repeated bounded attempts fail for the same external timing/observation reason rather than a changed implementation defect, cap further equivalent attempts and require redesign of the proof carrier or acceptance criterion before proceeding.

The exact budget should be shaped separately; this retrospective does not prescribe a universal numeric threshold.

### C. Lifecycle-completeness check

Before closing a parent delivery-control issue, enumerate associated shaping, promotion, implementation, remediation and deferred/backlog records and require an explicit disposition for each. Preserve intentionally parked work rather than auto-closing it.

### D. Machine-readable governed delivery state

Explore a small repository-owned state representation for current gate status and immutable identities so autonomous contexts do not need to recover every current decision from prose. Treat it as an index to authoritative evidence, not a substitute for review or authority.

### E. Consume exact live Pages verification automatically

Determine the relationship between `Publish CryptoPulse Pages`, `Verify CryptoPulse Live Pages` and close-out evidence. Where an exact successful live-verification result exists, bind it into the delivery record automatically or through a minimal deterministic adjudication step.

## Controls to retain

Efficiency improvements should not weaken the controls that materially contributed to the safe outcome:

- fail closed when decision-critical evidence is missing or ambiguous;
- retain immutable base/head/tree/evidence identities for consequential candidates;
- validate the exact candidate that is reviewed;
- preserve genuine fresh substantive review at the decisions that require independence;
- keep review disposition distinct from owner mutation/merge/activation authority;
- avoid mutable rolling branches as publication/evidence authority;
- do not represent unperformed live/network observations as completed proof;
- keep generated `_site/` output disposable and uncommitted;
- preserve the public AI-demo/non-advice posture.

## Retrospective conclusion

Phases 14 and 15 demonstrate that CryptoPulse's assurance model works: the project can stop safely when proof is incomplete, carry exact evidence through immutable boundaries and deliver a narrow public capability without uncontrolled scope expansion.

The next process improvement is to make that assurance model cheaper to operate. In particular, proof feasibility, lifecycle completeness and current governance state should become more machine-checkable so that future phases spend less effort reconstructing and repeating controls that can be evaluated deterministically.

That process work should not be selected automatically, and neither should any product successor. After this retrospective is accepted, its candidate improvements may be shaped into one umbrella governance-improvement issue and split further only where independent implementation boundaries justify it.
