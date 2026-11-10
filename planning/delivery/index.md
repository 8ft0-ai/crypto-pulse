# CryptoPulse delivery records

This directory contains post-delivery records for completed CryptoPulse phases and the pre-phase baseline that existed before formal phase-managed delivery started.

These files are not the canonical audit trail. The canonical audit trail remains the GitHub issue, pull-request, workflow-run, commit, and evidence-comment history. The delivery records are a curated management layer that makes completed work easier to understand without reconstructing it from GitHub history alone.

## Planning versus delivery

```text
planning/roadmap/  -> active or future phase planning
planning/delivery/ -> completed phase close-out records
planning/delivery-log.md -> concise chronological ledger
docs/              -> repository, product, and engineering docs
```

A roadmap phase spec should explain intended work before delivery. A delivery record should explain what actually shipped, what proved it, what artefacts were produced, and what boundaries were preserved.

## Baseline and completed phases

| Record | Primary outcome | Delivery record |
| --- | --- | --- |
| Pre-phase baseline | Preserves useful early repository history before formal phase-managed delivery, without pretending it was planned as a phase. | [pre-phase-baseline.md](pre-phase-baseline.md) |
| Phase 1 — Source evidence spine | Scheduled ingestion can produce a scoped `valid-ok` source snapshot PR. | [phase-01-source-evidence-spine.md](phase-01-source-evidence-spine.md) |
| Phase 2 — Deterministic report review loop | A merged `valid-ok` source snapshot can produce a reviewed deterministic Markdown report PR and render through the static site generator without committing `_site/`. | [phase-02-deterministic-report-review-loop.md](phase-02-deterministic-report-review-loop.md) |
| Phase 3 — Self-proving generated report PRs | Generated report PRs carry their own pre-PR proof, with downstream PR validation retained as defence in depth. | [phase-03-self-proving-generated-report-prs.md](phase-03-self-proving-generated-report-prs.md) |
| Phase 4 — Live-site provenance UX | The generated site leads with provenance, generation boundaries and schema-aware report presentation. | [phase-04-live-site-provenance-ux.md](phase-04-live-site-provenance-ux.md) |
| Phase 6 — Deterministic claim selection | Repository code compiles, ranks, reconstructs, validates and renders claim candidates without an LLM; deterministic selection remains the sole active selector after the bounded model comparison was closed. | [phase-06-deterministic-claim-selection.md](phase-06-deterministic-claim-selection.md) |
| Phase 9 — GPT-OSS quality and stability comparison | The governed GPT-OSS/DeepInfra comparison ends `no-stable-material-uplift`; deterministic selection remains the sole active selector and the temporary paid workflow is archived. | [phase-09-gpt-oss-quality-comparison.md](phase-09-gpt-oss-quality-comparison.md) |
| Phase 10 — Deterministic previous-hour comparison engine | Repository code produces deterministic fail-closed exact previous-hour comparison evidence under the frozen 3,600-second contract. | [phase-10-previous-hour-comparison.md](phase-10-previous-hour-comparison.md) |
| Phase 11 — Deterministic temporal visualisation | Repository code materialises, validates and deterministically renders repository-bound temporal series entirely offline. | [phase-11-deterministic-temporal-visualisation.md](phase-11-deterministic-temporal-visualisation.md) |
| Phase 12 — Canonical observation-hour evidence | Future source snapshots preserve actual timing while adding separately validated canonical containing-hour identity. | [phase-12-canonical-observation-hour-evidence.md](phase-12-canonical-observation-hour-evidence.md) |
| Phase 13 — Deterministic observation-hour comparison and temporal evidence | Phase-12 slot identity is consumed through exact adjacent-hour comparison and deterministic repository-bound temporal-series evidence. | [phase-13-observation-hour-temporal-evidence.md](phase-13-observation-hour-temporal-evidence.md) |
| Phase 14 — Deterministic site publication | Reviewed deterministic publication control plane and App/protection boundary delivered at a safe inert boundary; live stale-base proof, pilot and recurring activation deferred. | [phase-14-deterministic-site-publication.md](phase-14-deterministic-site-publication.md) |
| Phase 15 — Public deterministic temporal evidence | One validated repository-bound `BTC.price_usd` 24-slot temporal-evidence surface is published through the existing site pipeline with explicit gaps/provenance and demo/non-advice framing. | [phase-15-public-deterministic-temporal-evidence.md](phase-15-public-deterministic-temporal-evidence.md) |
| Phase 16 — Reader-facing evidence experience | Home, Most recent, Temporal evidence and Archive present one coherent reader experience while preserving distinct repository-owned evidence authorities. | [phase-16-reader-facing-evidence-experience.md](phase-16-reader-facing-evidence-experience.md) |
| Phase 17 — Trusted-main source-evidence accumulation and freshness | Immutable Phase-12-valid evidence can be accumulated into bounded source-only candidates, a real candidate has been promoted/proved, and daily candidate refresh is configured without automatic merge authority. | [phase-17-trusted-main-source-evidence-accumulation.md](phase-17-trusted-main-source-evidence-accumulation.md) |

Phase 1 remains the first formal phase-managed delivery phase. The pre-phase baseline is a historical record, not Phase 0.

Post-Phase 3 operating-model tidy-ups are tracked in the concise ledger rather than as separate phase records because they stabilise the operating model without creating a new delivery phase.

Phase 5 was an evaluation and architecture-transition programme rather than a separately closed delivery phase. Its evidence remains under `evaluation/phase-05/`, and its reviewed pivot into deterministic claim selection is captured by Phase 6 governance and delivery records.

Phase 9 is recorded without backfilling unrelated Phase 7 or Phase 8 delivery records. Its close-out is limited to the completed Phase 9 programme and does not reinterpret those earlier phase histories.

Phase 14 is recorded as complete at the safe inert control-plane boundary. Its delivery record explicitly preserves the unachieved live stale-base race, live pilot and recurring activation as deferred work rather than representing them as successful delivery.

Phase 15 is recorded as complete after the reviewed Slice 3 state was automatically deployed by the existing Pages workflow and the exact deployed artifact was verified. The record keeps Phase 14/#477 operationalisation and broader temporal-product work separately parked.

Phase 16 is recorded as complete after the final reader-facing integration was automatically deployed and the required public surfaces matched the deployed artifact byte-for-byte.

Phase 17 is recorded as complete after deterministic accumulation/recovery, the source-only candidate builder, one bounded real protected-main promotion, unchanged consumer/public proof and a separately governed daily candidate-refresh decision/implementation. The daily schedule may refresh a disposable candidate only; candidate/source merge authority remains exact-head and human-governed.

No successor phase is selected by the Phase 17 close-out.

## Structured delivery graph

The completed delivery history also has a small structured graph layer:

```text
delivery.yaml -> machine-readable delivery graph metadata
graph.md      -> generated Mermaid graph for GitHub review
```

Use the graph to navigate why phases happened, what each phase produced, and which issues, PRs, workflow runs, artefacts, boundaries, and lessons are connected.

The graph is a compact causal map. It is not a complete issue or pull-request inventory and should not model every generated snapshot PR, every small implementation PR, or every evaluation-only internal architecture slice individually.

For the modelling policy, see:

```text
graph-modelling-rules.md
```

The graph is validated by:

```bash
python scripts/validate_delivery_graph.py
```

The Mermaid output is regenerated by:

```bash
python scripts/render_delivery_graph.py
```

Phase 4, Phase 6, Phase 9 and Phase 14 explicitly record delivery-graph updates as not applicable under the compact causal-modelling rules. Their delivery records and the chronological ledger remain the management-level navigation for those phases. Phase 14 remains absent from the causal graph because it closes with publication activation disabled and adds no newly operational live publication stage.

Phase 15 is represented compactly because it closes the Phase 13 public-integration boundary and adds a durable public temporal-evidence surface. Phase 16 is represented because it adds an enduring reader-projection layer over those evidence authorities. Phase 17 is represented because it materially extends the trusted source-evidence spine and establishes the lasting boundary that recurring candidate refresh does not imply recurring merge authority. The graph intentionally keeps representative proof/artefact/boundary nodes rather than implementation or recovery inventories.

## Completed-phase record shape

Completed phase records should generally include:

```text
Status
Primary outcome
Parent issue
Linked issues / work breakdown
Key PRs
Final proof evidence
Produced artefacts
Validation evidence
Boundaries preserved
Carry-forward lesson
```

The shape is a guide rather than a rigid template. The record should stay readable and should avoid duplicating the concise ledger in full.

## Concise delivery ledger

For a compact chronological summary of completed phases and post-phase operating-model tidy-ups, see:

```text
../delivery-log.md
```
