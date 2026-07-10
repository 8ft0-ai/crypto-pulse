# Pre-phase baseline — before formal Phase 1

Status: complete.

This is a post-delivery baseline record for work that happened before formal phase-managed delivery began. It is not a reconstructed phase. It preserves useful history without pretending that the early repository work was planned as Phase 0.

Phase 1 remains the first formal phase-managed delivery phase.

## Primary outcome

Before Phase 1, CryptoPulse already had a working demo site, repository operating guidance, a PR-based delivery habit, early static-site UX improvements, a local source ingestion MVP, scheduled source ingestion automation, and snapshot-quality hardening.

That baseline made Phase 1 possible, but it was not itself a formal roadmap phase.

## Source inspected

The pre-phase baseline review inspected issue and PR history before #75.

Representative early issues:

```text
#1, #6, #7, #8, #11, #15, #16, #17, #18, #19, #20, #21, #27, #29, #30, #31, #32, #33, #34, #37, #44, #45, #63, #64, #65
```

Representative early PRs:

```text
#2, #3, #4, #5, #9, #10, #12, #13, #14, #22, #23, #24, #25, #26, #28, #35, #36, #38, #39, #40, #41, #42, #43, #46, #51, #53, #55, #57, #59, #62, #69, #70, #71
```

This record does not list every early item as graph metadata. The delivery graph should remain compact and explain why formal phase delivery started, not become a complete issue index.

## Classification

### Foundational

These items formed the repository baseline that Phase 1 later built on.

| Area | Issues / PRs | Why it matters |
| --- | --- | --- |
| Demo positioning and disclaimers | #1, #2, #3, #4 | Established that CryptoPulse is a demo/prototype and should not be mistaken for a live market-intelligence product. |
| Agent and repository guidance | #5, #10, #11, #14 | Created early workflow guidance and patch/write-strategy expectations for AI-assisted repository changes. |
| Static-site UX and archive foundations | #6, #7, #8, #12, #13, #15–#20, #23–#26, #29–#35, #39–#43 | Built the public demo/archive experience, report reading UX, search, metadata, source cards, and the canonical site-generator direction. |
| Source ingestion MVP | #44, #46 | Added the first local ingestion layer and source-snapshot validation without generating reports or calling an LLM. |
| Scheduled source ingestion automation | #45, #51, #53, #55, #57, #59 | Moved ingestion into GitHub Actions, created generated snapshot PRs, and hardened the workflow after early automation failures. |
| Snapshot evidence examples | #62, #70 | Proved that generated source snapshot PRs could be created and reviewed before the later valid-ok proof snapshot. |
| Snapshot quality hardening | #63, #64, #65, #69, #71 | Introduced source discovery, cross-check strategy, required/optional source criticality, and valid-ok / valid-degraded / invalid classification. |

### Process-learning

These items shaped the later IssueOps operating model.

| Area | Issues / PRs | Lesson carried forward |
| --- | --- | --- |
| PR-based delivery discipline | #21, #22 | Future implementation work should go through branch and PR review rather than direct commits to `main`. |
| Mechanical PR validation | #27, #28 | PR validation and `_site/` rejection became explicit controls. |
| Failed partial implementation and runbooks | #36, #37, #38 | Large-file edits, partial PRs, broad churn, and missing generator changes needed stronger agent guidance and safer editing discipline. |
| Patch/write-path constraints | #11, #14 | The repository documented a preferred patch workflow, but connector limitations still sometimes require contents-API fallback with clear PR disclosure. |

### Superseded

These items are useful history but should not be treated as current direction.

| Item | Why superseded |
| --- | --- |
| PR #2 | The initial demo-disclosure work was later reintroduced/completed by PR #3. |
| PR #36 | Closed and superseded because it was partial, CSS-only, conflicted, and did not implement the required generator changes. |
| Layered site build wrappers | Later consolidated behind the canonical `python -m site_generator` entry point. |
| Binance as a reliable GitHub-runner cross-check source | Discovery showed runner access problems; later quality work made exchange cross-checks optional/fallback-oriented. |

### Incidental

Some early work is real history but should not receive graph-level representation.

Examples include individual UX slices, report-card refinements, search/filter polish, accessibility improvements, generated snapshot examples, and small workflow diagnostics. These items are useful in PR history, but the delivery graph should not model them individually unless they explain a later delivery decision.

## Why this led to Phase 1

By the time #75 was opened, the repository had already learned several things:

- the demo needed durable disclaimers and product-boundary language;
- `_site/` had to remain generated output rather than source of truth;
- issue-to-branch-to-PR delivery was necessary for reviewable agent work;
- source ingestion could run in GitHub Actions and open snapshot PRs;
- source quality needed explicit classification before reports could safely consume snapshots;
- report generation should wait until the source-evidence spine was stable.

That is why Phase 1 should be understood as the first formal phase-managed delivery phase, not the beginning of the repository.

## Delivery graph treatment

The delivery graph should contain one compact pre-phase baseline node and one edge into Phase 1:

```text
pre-phase-baseline -> phase-1
label: enabled formal phase delivery
```

The detailed early inventory belongs in this Markdown record, not in the graph. For the general modelling policy, see:

```text
graph-modelling-rules.md
```

## Boundaries preserved

This baseline record does not change runtime behaviour. It does not alter report generation, source ingestion, static-site generation, generated reports, source snapshots, or site publication.

No generated `_site/` output is committed by this record.
