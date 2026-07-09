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

## Delivery graph

The structured delivery graph lives in:

```text
planning/delivery/delivery.yaml
```

It renders to:

```text
planning/delivery/graph.md
```

Validate the graph with:

```bash
python scripts/validate_delivery_graph.py
```

Regenerate the Mermaid graph with:

```bash
python scripts/render_delivery_graph.py
```
