# CryptoPulse planning

This directory is the planning control surface for CryptoPulse.

It is separate from `docs/` on purpose. `docs/` should contain repository, product, and engineering documentation. `planning/` contains the management artefacts used to plan, deliver, explain, and close out repository phases.

The GitHub issue, pull-request, workflow-run, commit, and evidence-comment history remains the canonical audit trail. These planning files are a curated navigation layer over that history.

## Structure

```text
planning/roadmap/  -> forward-looking phase specs and templates
planning/delivery/ -> completed phase close-out records and graph metadata
planning/delivery-log.md -> concise chronological ledger
```

## How to use this folder

Start new phase work in `planning/roadmap/`. A roadmap spec should explain the intended problem, goal, non-goals, target workflow, acceptance gates, risks, and definition of done before delivery starts.

After a phase is complete, record what actually shipped in `planning/delivery/`. A delivery record should explain the issues and PRs that implemented the phase, the workflow runs that proved it, the artefacts produced, the validation that passed, the boundaries preserved, and the lessons that carry forward.

Keep `planning/delivery-log.md` concise. It is the chronological ledger, not the full narrative record.

## Phase close-out checklist

A PR that closes a delivery phase should update, or explicitly mark as not applicable, the following planning assets:

```text
planning/delivery/<phase>.md
planning/delivery-log.md
planning/delivery/delivery.yaml
planning/delivery/graph.md
```

If the phase changes future direction, also update the relevant roadmap files:

```text
planning/roadmap/index.md
planning/roadmap/<phase-or-next-phase>.md
```

Do not update roadmap specs for every small implementation PR. Use roadmap updates when planning intent, scope, acceptance gates, or next-phase direction changes. Use delivery updates when recording what actually shipped.

Raw Markdown reports remain the source of truth. Generated `_site/` output remains disposable and must not be committed.

## Delivery graph

The structured delivery graph lives in:

```text
planning/delivery/delivery.yaml
```

It renders to:

```text
planning/delivery/graph.md
```

The graph explains causality and proof. It should show why the system changed direction, what proved a phase, what artefacts became dependencies, and what boundaries or lessons carried forward. It is not a complete issue or pull-request inventory, and it must not replace GitHub history.

For modelling policy, see:

```text
planning/delivery/graph-modelling-rules.md
```

Validate the graph with:

```bash
python scripts/validate_delivery_graph.py
```

Regenerate the Mermaid graph with:

```bash
python scripts/render_delivery_graph.py
```

When `planning/delivery/delivery.yaml` changes, `planning/delivery/graph.md` must be regenerated and committed in the same PR.
