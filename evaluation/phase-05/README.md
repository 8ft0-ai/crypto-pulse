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

The free-model option is therefore closed for Phase 5. ZDR, data-collection denial, disabled cross-model fallback and disabled automatic generation remain unchanged.

## GPT-4o mini public-data proof

The project then approved a narrowly isolated public-data demonstration using `openai/gpt-4o-mini`, ordinary provider retention, denied data collection, strict structured output and no cross-model fallback.

- Reviewer-visible decision: [`public-demo-decision.md`](public-demo-decision.md)
- Machine-readable decision: [`public-demo-decision.yml`](public-demo-decision.yml)
- Source diagnostic run: [29151358149](https://github.com/8ft0-ai/crypto-pulse/actions/runs/29151358149)

The run completed route preflight, smoke generation and all ten frozen corpus calls through actual provider `OpenAI`. The core capability proof succeeded: GPT-4o mini consumed governed evidence and produced schema-valid, evidence-referenced, policy-compliant responses, including safe handling of the prompt-injection case.

The current model-authored natural-prose contract nevertheless received only `1/10` hard passes. The reviewed outcome is **`public-demo-no-go` for that contract**, not an intrinsic model no-go. Most failures came from stochastic numeric presentation and claim-taxonomy selection rather than unsupported facts.

Issue #228 then shaped a semantic claim-plan contract with deterministic repository-owned prose rendering.

## Semantic claim-plan model selection and calibration

The semantic contract moved model responsibility from final report prose to a bounded claim plan. Repository code owns evidence validation, claim support, deterministic rendering and publication authority.

The subsequent model-selection work compared GPT-5.6 Sol, Nex N2 Mini and MiniMax M3, but the discovery process also exposed defects and assumptions in the evaluation machinery itself. Protected runs identified:

- a classification-map setup defect before any model call;
- an undersized GPT-5.6 per-call cost ceiling;
- a weak route probe that did not represent the real message shape;
- a Nex provider requirement for a user-role message;
- MiniMax output-length exhaustion followed by a fair semantic-taxonomy failure;
- cross-source price-field normalisation that was missing from the evidence contract;
- invalid soft scoring for validator-rejected and missing plans;
- workflow names similar enough to cause the superseded three-model calibration to be dispatched again.

The full chronology, technical findings and self-reflection are recorded in [`semantic-model-evaluation-retrospective.md`](semantic-model-evaluation-retrospective.md).

Current status:

- no model has been selected;
- GPT-5.6 Sol remains benchmark-only;
- Nex N2 Mini remains the affordable candidate pending one fair corrected full-contract call;
- MiniMax M3 does not advance;
- North Mini Code remains catalogue-ineligible;
- automatic generation and publication remain disabled;
- issue #269 remains open until the prompt-v2 final two-call artefact is reviewed.

The active final calibration workflow is **Semantic plan calibration — GPT-5.6 + Nex only** and now uses `crypto-market-claim-plan/v2`. A successful calibration would prove compatibility, not complete production selection. Repeated multi-case evidence and a separately reviewed decision would still be required.

## Five-model catalogue expansion screen

Issue #273 introduced a separate screen for DeepSeek V4 Flash, GPT-5.6 Luna, Qwen3.6 Flash, MiMo V2.5 Pro and Seed 2.0 Mini. Protected run [`29246391801`](https://github.com/8ft0-ai/crypto-pulse/actions/runs/29246391801) completed against trusted `main` SHA `5bb4c8a8c9816353fee6487eb39f7906333ffada` for USD 0.0200591105.

The reviewed outcome is recorded in [`catalogue-screen-29246391801.md`](catalogue-screen-29246391801.md):

- Luna completed a compact plan but exposed an unstated validator rule for one source subject per `source_status` claim;
- DeepSeek reached a provider route but exhausted an unrepresentative 16-token reasoning probe;
- Qwen exhausted its 4,000-token full-contract allowance;
- MiMo had no endpoint eligible for the complete governed request and policy;
- Seed completed fairly but failed multiple semantic taxonomy rules.

The original five-model workflow is removed from the Actions UI. Its runner, configuration, documentation, Git history and protected artefacts remain available for audit.

## Prompt-v2 corrective screen

Issue #275 adds the immutable `crypto-market-claim-plan/v2` prompt. It preserves prompt v1 and makes the validator's source grouping rule explicit:

> A `source_status` claim must describe exactly one source subject. Every cited evidence record in that claim must belong to that same source subject. Use separate claims for separate sources.

The corrective workflow **Semantic plan correction — Luna + DeepSeek + Qwen** gives Luna, DeepSeek and Qwen one corrected route probe and one full-contract call over the same normalised `historical-normal-crosschecked` evidence. It has a USD 0.10 hard ceiling, no leaderboard, no deployment selection, no automatic generation and no publication.

MiMo and Seed remain excluded from that corrective run for the reviewed reasons above.

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

The final free-model follow-up uses a separate immutable configuration, `config/llm-evaluation-free-proof.yml`, so the original two-model plan and its reviewed no-go remain independently reproducible.

The GPT-4o mini public-data path uses a separate profile and paid benchmark configuration so its public-input policy exception and reviewed evidence remain independently auditable.

The later semantic model-selection and calibration configurations remain retained as historical evaluation artefacts. Obsolete manual workflow entry points may be removed without deleting their runners, configurations, Git history or protected run evidence.

At execution time the workflows check the public OpenRouter catalogue again. A disappeared, expired, incorrectly priced or structured-output-ineligible model is recorded as ineligible rather than silently replaced.

## Operating sequence

```text
merge evaluation harness
manually dispatch protected evaluation from main
review evaluation artefacts and reviewer worksheet
commit the approved decision in a separate review PR
```

For future candidates, the evaluation sequence is now more explicit:

```text
catalogue eligibility
representative route probe
one real full-contract smoke call
repeated single-case calibration
multi-case evaluation
reviewed decision
```

The separate decision PR is required because pull-request code must not receive `OPENROUTER_API_KEY`, and workflow artefacts must be reviewed before a production-proof configuration is selected.
