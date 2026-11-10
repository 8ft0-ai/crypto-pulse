# Phase N — Short phase name

Status: shaping.

This is a forward-looking roadmap spec. It should describe intended work before delivery. After the phase is delivered, close-out evidence should move into `planning/delivery/` as a completed delivery record.

## Problem statement

Describe the operational, product, evidence, or maintenance problem this phase exists to solve.

## Goal

State the primary outcome the phase should prove.

## Non-goals

List explicit exclusions so the phase does not expand beyond its intended boundary.

```text
No committed _site output.
No auto-merge unless explicitly approved.
No auto-publish unless explicitly approved.
No secrets or paid API keys unless explicitly approved.
```

Adjust this list for the phase, but keep repository-level safety and demo boundaries intact.

## Target workflow or target state

Describe the desired workflow, architecture, data flow, documentation state, or operating model.

```text
step one
step two
step three
```

## Acceptance gates

A phase is only complete when it can prove the intended outcome.

- [ ] Gate one.
- [ ] Gate two.
- [ ] Gate three.

## Proposed implementation slices

Use linked issues rather than relying on native GitHub sub-issues.

```text
1. Parent phase issue
2. First implementation issue
3. Second implementation issue
4. Proof issue
5. Close-out evidence issue
```

## Risks and mitigations

### Risk: Example risk

Mitigation: explain how the phase controls or reduces the risk.

## Definition of done

The phase is complete when:

- [ ] the parent issue and linked child issues exist;
- [ ] implementation PRs are merged;
- [ ] the proof issue records concrete evidence;
- [ ] close-out evidence is added to the parent issue;
- [ ] the delivery record is added under `planning/delivery/`;
- [ ] `planning/delivery-log.md` is updated if the phase should appear in the concise ledger;
- [ ] `planning/delivery/delivery.yaml` is updated, or explicitly marked not applicable;
- [ ] `planning/delivery/graph.md` is regenerated when `delivery.yaml` changes;
- [ ] `planning/roadmap/` is updated only if roadmap intent, scope, acceptance gates, or next-phase direction changed;
- [ ] generated `_site/` output is not committed.

## Close-out PR checklist

For the PR that closes this phase:

- [ ] Update `planning/delivery/<phase>.md`.
- [ ] Update `planning/delivery-log.md`.
- [ ] Update `planning/delivery/delivery.yaml`.
- [ ] Regenerate `planning/delivery/graph.md`.
- [ ] Update `planning/roadmap/` only if roadmap intent or next-phase direction changed.
- [ ] Confirm raw Markdown reports remain the source of truth.
- [ ] Confirm generated `_site/` output is not committed.

## Follow-on delivery record

At close-out, create or update:

```text
planning/delivery/phase-N-short-phase-name.md
```

The completed delivery record should explain what actually shipped, what proved it, what artefacts were produced, and what boundaries were preserved.
