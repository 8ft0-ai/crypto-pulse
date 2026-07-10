# Delivery graph modelling rules

Status: active guidance.

This file defines how to keep the CryptoPulse delivery graph focused, useful, and maintainable.

## Purpose

The delivery graph explains causality and proof. It is a compact navigation layer over the repository delivery history, not a complete inventory of every issue, pull request, commit, or workflow run.

```text
GitHub issues / PRs / commits / workflow runs = canonical audit trail
planning/delivery/*.md                        = readable delivery records
planning/delivery/delivery.yaml               = compact causal graph metadata
planning/delivery/graph.md                    = generated visual navigation layer
```

Use GitHub when the question is, “What exactly happened?” Use delivery records when the question is, “What shipped and what proved it?” Use the graph when the question is, “Why did this phase lead to that phase?”

## What the graph should model

Add or keep a node when it materially explains the delivery story.

Model a node when:

- it explains why the system changed direction;
- it is the key proof for a phase;
- it captures an enduring boundary, risk, or carry-forward lesson;
- it is a produced artefact that future phases depend on;
- it represents a parent phase issue or close-out PR that anchors delivery evidence;
- it captures a problem or decision that motivated a later phase.

Good graph nodes usually answer one of these questions:

```text
Why did this happen next?
What proved that this phase worked?
What artefact became a dependency?
What boundary did we preserve?
What lesson carried forward?
```

## What the graph should not model

Do not add graph nodes just because work happened.

Do not model:

- every generated source snapshot PR;
- every generated report PR;
- every small implementation PR if the parent phase record already captures it;
- every early or pre-phase PR individually;
- incidental cleanup that does not change the operating model;
- exploratory work that was abandoned and has no carry-forward lesson;
- duplicate evidence when one representative proof node is enough;
- routine CI runs unless a workflow run is the key proof for a phase.

The graph should not replace GitHub search, GitHub issue history, pull-request history, commit history, or workflow-run history.

## Generated snapshot PR rule

Generated source snapshot PRs are operational evidence, but they should not normally become individual graph nodes.

Model a generated snapshot PR only when it is the representative proof for a phase or when it changes the delivery model. Otherwise, record it in the relevant delivery record or issue comment and leave it out of the graph.

This keeps the graph from being overwhelmed by scheduled ingestion churn.

## Pre-phase history rule

Early repository history should be preserved without pretending that every early item was part of a planned phase.

The pre-phase baseline is deliberately represented by one compact node:

```text
pre-phase-baseline -> phase-1
label: enabled formal phase delivery
```

Do not model every early issue or PR individually. Put the detailed early inventory in `planning/delivery/pre-phase-baseline.md` and use the graph only to show how that baseline enabled formal phase-managed delivery.

## Phase close-out rule

When a phase closes, update the graph only if the close-out changes the causal delivery story.

A close-out PR should usually update:

```text
planning/delivery/<phase>.md
planning/delivery-log.md
planning/delivery/delivery.yaml
planning/delivery/graph.md
```

But it should keep `delivery.yaml` compact. Prefer one parent phase node, one key proof PR, one key workflow run, one produced artefact, one boundary, or one lesson over a complete list of all child PRs.

## Delivery graph update checklist

Before adding a node, ask:

- Does this node explain why the system changed direction?
- Is this node the strongest proof for a phase?
- Will future readers need this node to understand the next phase?
- Is this better represented in a delivery Markdown record instead?
- Would adding every similar item make the graph noisy?

If the answer is mostly “no”, do not add the node.

## Boundaries

This policy does not change runtime behaviour. It does not alter source ingestion, report generation, generated reports, static-site generation, delivery graph schema, or site publication.

Generated `_site/` output remains disposable and must not be committed.
