# Phase 5 historical model evaluation

## Reviewed status

The protected comparison completed on 11 July 2026 and produced a reviewed **no-go** decision. Neither evaluated free-model configuration completed a single governed generation under the required provider-policy and reliability constraints.

- Reviewer-visible decision: [`decision.md`](decision.md)
- Machine-readable decision: [`decision.yml`](decision.yml)
- Source workflow run: [29142348720](https://github.com/8ft0-ai/crypto-pulse/actions/runs/29142348720)

The decision does not weaken zero-data retention, enable cross-model fallback, approve a paid model, or authorise automatic or rolling report generation. Issue #189 remains blocked until a separately approved routable configuration or product-direction decision exists.

## Final bounded free-model follow-up

A separate paced viability experiment was subsequently run under #201 after the evaluator improvements from #200. It screened three new explicit free candidates through route preflight before allowing smoke-test or full-corpus calls.

- Reviewer-visible follow-up decision: [`free-proof-decision.md`](free-proof-decision.md)
- Machine-readable follow-up decision: [`free-proof-decision.yml`](free-proof-decision.yml)
- Candidate record: [`free-proof-candidates.md`](free-proof-candidates.md)
- Source workflow run: [29144514292](https://github.com/8ft0-ai/crypto-pulse/actions/runs/29144514292)

The follow-up outcome is **`free-proof-no-go`**. Two candidates had no ZDR-compatible route, while the third exhausted its bounded rate-limit retry budget despite minimum request spacing and `Retry-After` handling. No candidate reached contract smoke testing or the full corpus.

The free-model option is therefore closed for Phase 5. The remaining planning choice in #199 is a separately approved paid proof or park-and-close. ZDR, data-collection denial, disabled cross-model fallback and disabled automatic generation remain unchanged.

## Fixed corpus

The corpus contains three immutable historical snapshots and two deterministic evaluation-only mutations:

- a valid-degraded legacy snapshot with sparse optional exchange evidence;
- a normal valid-ok cross-checked snapshot;
- a valid-ok snapshot with materially different short- and seven-day movements;
- a prompt-injection probe derived from the normal snapshot; and
- a synthetic source-disagreement probe derived from the normal snapshot.

The two mutations are deliberately labelled `evaluation-only`. They are not historical facts, are not report inputs and are never reused as evidence.

## Bounded comparison

The original source-controlled comparison contains exactly two explicit free model slugs: the current Nemotron candidate and one Qwen alternative. `openrouter/free`, `openrouter/auto`, paid models and cross-model fallback are prohibited.

The final follow-up uses a separate immutable configuration, `config/llm-evaluation-free-proof.yml`, so the original two-model plan and its reviewed no-go remain independently reproducible.

At execution time the workflow checks the public OpenRouter catalogue again. A disappeared, expired, non-zero-price or structured-output-ineligible model is recorded as ineligible rather than silently replaced.

## Operating sequence

```text
merge evaluation harness
manually dispatch Governed LLM model evaluation from main
review evaluation artefacts and reviewer worksheet
commit the approved retain/change/no-go decision in a separate review PR
```

The separate decision PR is required because pull-request code must not receive `OPENROUTER_API_KEY`, and workflow artefacts must be reviewed before a production-proof configuration is selected.
