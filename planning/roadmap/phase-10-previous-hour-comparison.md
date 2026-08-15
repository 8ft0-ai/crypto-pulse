# Phase 10 — Deterministic previous-hour comparison engine

Status: shaping.

Roadmap rebaseline issue: #398

This is a forward-looking roadmap specification. It records the owner-approved post-Phase-9 direction only. It does not authorise implementation, workflow changes, provider/model use, report integration, publication changes or rolling snapshot automation changes.

## Problem statement

CryptoPulse already archives validated hourly source snapshots and has repository-owned deterministic report and claim semantics, but it does not yet have a canonical deterministic contract for answering a basic temporal evidence question:

> What changed between the current validated snapshot and its valid predecessor?

Without that layer, downstream reporting can describe current-state evidence but cannot rely on a repository-owned comparison record that proves which two snapshots were compared, whether the interval is valid, which metrics are comparable, what changed and what could not be compared.

The missing capability should be solved deterministically before reopening any model-selection or model-authored narrative work.

## Goal

Prove a deterministic, fail-closed comparison path over exactly two repository-owned snapshot inputs:

1. one current validated snapshot;
2. one uniquely resolved valid predecessor under a predeclared predecessor/time-gap policy.

The phase should produce structured comparison evidence with complete provenance to both inputs, deterministic identity and ordering, explicit comparison availability/status, and metric-level handling that never fabricates continuity or coerces missing data into market movement.

The phase is successful when the repository can reproduce the same validated comparison evidence from the same two snapshots with zero provider/model calls.

## Design gate before implementation

The phrase `previous-hour` must not silently imply a timing tolerance.

Before implementation work begins, a separately governed design/delivery-control issue must freeze the predecessor-resolution contract, including:

- the authoritative snapshot timestamp/identity field used for ordering;
- whether the predecessor must be exactly one hour earlier or may fall within a bounded interval;
- the exact lower/upper elapsed-time bounds if a tolerance is allowed;
- how ties or multiple equally eligible predecessors are handled;
- whether schema/version compatibility affects eligibility;
- whether degraded-but-valid snapshots are eligible;
- the exact fail-closed result when no unique eligible predecessor exists.

No implementation issue may invent or widen this policy after seeing fixture or runtime results. If current repository evidence is insufficient to predeclare the rule, the design gate should stop rather than infer one.

## Comparison boundary

The engine should accept only repository-owned snapshot inputs that satisfy the existing snapshot-validity contract.

It should compare only fields whose meaning is already defined and is compatible across both snapshots. Candidate comparison families include, where the existing snapshot contract actually supports them:

- asset price/direction/change evidence;
- volume evidence;
- market-cap or dominance evidence;
- liquidation evidence;
- source availability/status changes.

This list is a boundary, not a requirement to manufacture unsupported metrics. A field that is absent, invalid, semantically incompatible or unavailable on either side is not comparable and must remain explicitly unavailable.

Source appearance/disappearance is source-availability evidence. It must not be interpreted as market movement.

## Required structured evidence

The exact schema belongs to a later implementation design slice, but every accepted comparison record must retain enough information to prove at minimum:

```text
comparison schema/version
current snapshot identity/path
definitive current timestamp
predecessor snapshot identity/path
definitive predecessor timestamp
elapsed interval
predecessor-resolution policy/version
input validation status
comparison status
metric comparison records
source-availability change records
stable deterministic comparison identity
stable deterministic ordering
```

Each metric comparison should distinguish at least:

```text
comparable
unavailable-current
unavailable-predecessor
invalid-current
invalid-predecessor
incompatible
```

The final implementation may use equivalent source-controlled names, but it must preserve these semantic distinctions and remain fail closed.

## Target deterministic path

```text
repository-owned current snapshot
    ↓
existing snapshot validation
    ↓
canonical predecessor resolution
    ↓
repository-owned predecessor snapshot
    ↓
existing snapshot validation
    ↓
compatibility / comparability checks
    ↓
deterministic metric and source-availability comparison
    ↓
comparison-record validation
    ↓
stable structured comparison evidence
```

No provider/model boundary belongs in this path.

## Fail-closed behaviour

The phase must not fabricate continuity. The comparison must fail closed or become explicitly unavailable when:

- no eligible predecessor exists;
- more than one predecessor is equally eligible under the frozen rule;
- either input fails the existing snapshot-validity contract;
- required snapshot identity or timestamp evidence is missing/ambiguous;
- elapsed time violates the frozen predecessor policy;
- snapshot schema or field semantics are incompatible;
- a metric cannot be compared safely across the pair.

Metric-level unavailability must not automatically invalidate unrelated comparable metrics when the record can safely express the distinction. Conversely, an input-level provenance, validity or predecessor-resolution failure must prevent a misleading partially trusted comparison record.

Missing numeric data must never be coerced to zero. Source availability changes must never be converted into price, volume, dominance or liquidation changes.

## Proof corpus

Before any product integration, prove the engine using repository-owned historical snapshots and/or committed deterministic fixtures that cover at minimum:

1. normal consecutive valid snapshots;
2. material metric change;
3. non-material or unchanged metric;
4. metric missing on the current side;
5. metric missing on the predecessor side;
6. source availability gained;
7. source availability lost;
8. missing predecessor;
9. ambiguous predecessor;
10. invalid current snapshot;
11. invalid predecessor snapshot;
12. incompatible schema/field semantics;
13. elapsed interval outside the frozen rule;
14. deterministic repeatability with stable ordering and identity.

Fixtures must not require a live provider/model call. The proof should make exact input identities and expected comparison outputs reviewer-visible.

## Acceptance gates

- [ ] A separate delivery-control/design issue freezes the canonical predecessor-resolution and elapsed-time policy before implementation.
- [ ] The implementation accepts exactly one current snapshot and one uniquely resolved predecessor as its comparison pair.
- [ ] Both inputs are validated through the existing repository-owned snapshot-validity boundary.
- [ ] Comparison evidence retains exact provenance to both inputs and their canonical timestamps/identities.
- [ ] A versioned structured comparison contract exists and is validated fail closed.
- [ ] Only semantically compatible fields are compared.
- [ ] Missing, invalid and incompatible metrics remain explicitly unavailable and are never coerced to zero.
- [ ] Source availability gain/loss is represented separately from market movement.
- [ ] Comparison identity and ordering are deterministic across repeated execution of the same inputs.
- [ ] The required proof corpus covers success, ambiguity, absence, invalidity and incompatibility cases.
- [ ] Proof requires zero provider/model calls and no credentials.
- [ ] Existing deterministic selector behaviour is unchanged.
- [ ] Existing source snapshot contents and rolling snapshot automation are unchanged.
- [ ] No automatic report generation, scheduling, publication or auto-merge behaviour is added.
- [ ] No generated `_site/` output is committed.

## Non-goals

Phase 10 does not authorise:

```text
No change to scheduled or rolling source snapshot automation.
No generation or merge of a new source snapshot as part of implementation proof.
No modification of historical source snapshots.
No automatic report-generation integration.
No report publication or auto-merge change.
No model/provider evaluation or invocation.
No reopening of Phase 9 or creation of another Phase 9 recovery authority.
No change to the deterministic candidate selector.
No model-authored claims, rationale, causality, sentiment or prose.
No news or event ingestion.
No chart or public market-card implementation.
No support/resistance, signal, target, watchlist or trading-guidance logic.
No automatic sentiment/risk taxonomy.
No secrets or paid API keys.
No committed generated `_site/` output.
```

A later phase may consume validated comparison evidence only after this deterministic capability is proved and separately closed.

## Proposed implementation slices

These are planning candidates only. Do not create or execute them without separate owner authority after this roadmap candidate is independently reviewed and merged.

```text
1. Phase 10 delivery-control/design issue
   - freeze predecessor/time-gap policy
   - freeze comparison schema and fail-closed semantics

2. Deterministic predecessor resolver
   - locate exactly one eligible predecessor
   - prove missing/ambiguous/out-of-window rejection

3. Comparison record and validator
   - provenance, identity, ordering and status contract
   - metric-level comparability semantics

4. Deterministic metric/source comparison adapters
   - only existing supported snapshot semantics
   - explicit source-availability transitions

5. Offline proof corpus and repeatability evidence
   - normal, degraded, missing, ambiguous, invalid and incompatible cases
   - zero provider/model calls

6. Phase 10 close-out
   - delivery record and concise ledger update
   - delivery-graph disposition under existing modelling rules
```

No report/site integration slice is part of Phase 10.

## Risks and mitigations

### Risk: `previous-hour` becomes an implicit or moving time-window rule

Mitigation: freeze the timestamp source, eligibility rule and elapsed-time bounds in a separately reviewed design gate before implementation. Do not widen them after observing results.

### Risk: irregular snapshots are treated as continuous hourly evidence

Mitigation: require unique predecessor eligibility and retain the exact elapsed interval in every accepted record. Missing or out-of-policy predecessors fail closed.

### Risk: missing metrics become false zero moves

Mitigation: use explicit unavailable/invalid/incompatible states. Never coerce missing numeric evidence to zero.

### Risk: source outages are interpreted as market changes

Mitigation: model source availability as a separate deterministic evidence family and prohibit it from being converted into market-movement evidence.

### Risk: schema drift makes historical/current fields look comparable when they are not

Mitigation: require explicit schema/field semantic compatibility before comparison and retain incompatibility as a first-class status.

### Risk: Phase 10 becomes a back door to model evaluation or publication changes

Mitigation: keep the target path credential-free, structured and deterministic; exclude provider/model calls, report integration, scheduling and publication from the phase.

## Definition of done

Phase 10 is complete only when:

- [ ] the separately authorised parent delivery-control issue and bounded child issues exist;
- [ ] the predecessor/time-gap policy was frozen before implementation;
- [ ] implementation PRs are merged after exact-head validation and review;
- [ ] offline proof records concrete input/output and repeatability evidence;
- [ ] no provider/model call or credential was required;
- [ ] source snapshot automation and deterministic selector state remained unchanged;
- [ ] the Phase 10 delivery record is added under `planning/delivery/`;
- [ ] `planning/delivery-log.md` is updated;
- [ ] `planning/delivery/delivery.yaml` is updated, or explicitly marked not applicable under the existing compact graph rules;
- [ ] `planning/delivery/graph.md` is regenerated if `delivery.yaml` changes;
- [ ] roadmap/backlog state is reconciled after close-out;
- [ ] generated `_site/` output is not committed.

## Follow-on delivery record

At close-out, create:

```text
planning/delivery/phase-10-previous-hour-comparison.md
```

The completed delivery record should state what comparison contract actually shipped, the exact predecessor policy, proof inputs/results, validation evidence, preserved boundaries and any separately governed follow-on candidate.
