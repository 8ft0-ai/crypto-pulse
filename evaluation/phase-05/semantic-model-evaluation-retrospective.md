# Semantic claim-plan model evaluation retrospective

Date: 13 July 2026.

Status: discovery and harness hardening recorded; final GPT-5.6 Sol versus Nex N2 Mini calibration still pending.

This record captures what CryptoPulse learned while trying to select a model for the constrained semantic claim-plan contract. It is intentionally separate from a model-selection decision. No production model has been selected, automatic generation remains disabled, publication remains disabled, and the deterministic evidence and rendering path remains the authority.

## Why this record exists

The work produced useful model evidence, but it also exposed weaknesses in the evaluation process itself. Several protected runs were required before the project could distinguish model behaviour from harness defects, provider incompatibility, cost calibration, evidence-normalisation problems and workflow-selection mistakes.

The central lesson is:

> A model evaluation harness must itself be calibrated before it is allowed to evaluate models.

The GitHub issue, pull-request, workflow-run and retained-artefact history remains the canonical audit trail. This document is the curated explanation a future reviewer should read before reconstructing that history.

## Work completed

The semantic claim-plan path was introduced to replace model-authored report prose with a bounded model-owned plan and deterministic repository-owned rendering. The contract requires exact evidence references, restricted intent and comparison taxonomies, fail-closed semantic validation, byte-identical deterministic rendering, exact model identity, explicit provider evidence, disabled cross-model fallback and bounded cost.

The model-selection work was delivered through:

- issue #263 and PR #264 — initial GPT-5.6 Sol, Nex N2 Mini and MiniMax M3 Stage 1 evaluation harness;
- issue #265 and PR #266 — correction of the classification-map setup failure;
- issue #267 and PR #268 — one-call-per-model compatibility calibration with retained provider diagnostics and progress logging;
- issue #269 and PR #270 — final two-model calibration with canonical price normalisation, Nex message compatibility and validator-gated quality scoring;
- issue #271 — this retrospective and workflow cleanup.

The historical runners, configurations and artefacts are retained for audit. They are not all active workflows.

## Protected-run chronology

| Run | Intended purpose | What actually happened | Decision value |
| --- | --- | --- | --- |
| [`29230276601`](https://github.com/8ft0-ai/crypto-pulse/actions/runs/29230276601) | First three-model Stage 1 evaluation | The runner failed during setup because a validated classification mapping was incorrectly iterated as a sequence of records. No candidate route probe or substantive generation occurred. | Infrastructure evidence only. Zero model calls and zero model cost. |
| [`29231039012`](https://github.com/8ft0-ai/crypto-pulse/actions/runs/29231039012) | Corrected 50-generation Stage 1 evaluation | All configured generations were attempted, but the run mixed genuine semantic failures with provider incompatibility, output-length exhaustion, an undersized GPT-5.6 per-call cap and invalid quality scoring for empty failures. Observed model cost was approximately USD 0.3471. | Useful discovery evidence, but not a fair model-selection result. |
| [`29235513924`](https://github.com/8ft0-ai/crypto-pulse/actions/runs/29235513924) | One full-contract compatibility call per shortlisted model | GPT-5.6 completed but exposed cross-source field-normalisation mismatch; Nex exposed a provider requirement for a user-role message; MiniMax completed after an output-limit increase but failed the semantic intent taxonomy. Observed cost was approximately USD 0.1045. | Valid compatibility evidence. MiniMax did not advance; GPT-5.6 and Nex required bounded corrections. |
| [`29242343644`](https://github.com/8ft0-ai/crypto-pulse/actions/runs/29242343644) | Intended final GPT-5.6/Nex calibration | The superseded three-model workflow was accidentally dispatched because its name was too similar to the new final workflow. It repeated the earlier calibration shape, including MiniMax, without the new evidence normalisation or Nex user message. Observed cost was approximately USD 0.1053. | No new model-decision evidence. It is evidence of a repository workflow-UX defect. |

The correct final two-call calibration has not yet been run at the time of this record.

## What the model evidence currently says

### GPT-5.6 Sol

GPT-5.6 demonstrated that it can complete the real structured claim-plan request, preserve the requested route and produce materially useful plans. The original Stage 1 result understated capability because half of its calls were rejected by a USD 0.10 per-call ceiling that sat below realistic completion cost.

The one-call calibration then exposed a contract-normalisation problem rather than a clear reasoning failure: CoinGecko USD spot evidence used the field name `price_usd`, while Coinbase Exchange used `price`. Those records represented the same economic measure and unit, but the validator correctly required canonical compatibility. The final harness now derives a content-addressed bundle that normalises Coinbase USD spot `price` to `price_usd` while preserving evidence IDs, values, units, source identity, source paths and provenance.

GPT-5.6 also tended to select too many claims. Even if it validates in the final calibration, restraint and materiality remain evaluation concerns rather than assumed strengths.

### Nex N2 Mini

Nex passed a small structured-output route probe, but every original full-contract request failed before semantic evaluation. The retained diagnostic eventually identified the exact provider response: `No user query found in messages.`

The production request had placed the governed prompt and evidence in a system message without a user message. The simple route probe used a user-role message, so the probe was not representative of the real request. The final harness preserves the governed system prompt and adds one fixed execution message for Nex only when no user message already exists.

Nex has therefore not yet received a fair semantic evaluation of the corrected full contract.

### MiniMax M3

MiniMax originally exhausted a 4,000-token output allowance and returned `finish_reason: length`. Increasing the allowance to 8,000 tokens resolved the transport-level truncation and produced a complete structured response.

The completed response nevertheless failed the central semantic taxonomy. It used `snapshot_status` and `source_status` for ordinary market observations and produced multiple unsupported claim combinations. That was a fair full-contract semantic failure. MiniMax does not advance to the final calibration.

### North Mini Code

Cohere North Mini Code remained catalogue-ineligible because the current OpenRouter listing did not advertise the strict structured-output parameters required by the contract. It received no generation call.

## What worked well

The repository consistently failed closed. Invalid plans were not silently rendered or promoted. Exact requested model identity, actual provider evidence, fallback behaviour, token usage, cost and protected raw completions were retained where providers supplied them.

The process also learned to separate several states that superficial model benchmarks often collapse:

- infrastructure failure;
- catalogue or route ineligibility;
- minimal route-probe success;
- full-contract provider compatibility;
- semantic-validator acceptance;
- deterministic-render acceptance;
- case-expectation quality;
- cost and latency viability.

That separation prevented the project from declaring a winner based on misleading partial evidence.

## Where the process was weak

### The paid evaluation began before compatibility calibration

The 50-generation run should not have been the first test of the real schema, real message-role structure, realistic output length, realistic per-call cost and provider error retention. One representative full-contract call per candidate would have found most of those problems earlier, faster and more cheaply.

### The route probe was too weak

The probe answered whether the route could return some structured JSON. It did not prove that the route could execute the actual CryptoPulse prompt, message shape, projected schema and output envelope. Nex passed the probe and rejected the real request, showing that minimal route success is not full-contract compatibility.

### Configuration assumptions were treated as facts

The process initially assumed that USD 0.10 was sufficient for GPT-5.6, 4,000 tokens were sufficient for MiniMax, equivalent price measures would share one field name, all providers would accept a system-only conversation, and identical empty failures could be treated as stable. These should have been explicit hypotheses tested during calibration.

### Quality scoring was not subordinate to validity

Rejected and missing plans initially received semantic coverage, materiality, restraint and stability values. Identical empty failures therefore appeared perfectly stable and retained a misleading fraction of benchmark quality.

The corrected invariant is:

```text
validator acceptance is a prerequisite for every soft quality metric
```

Rejected or missing plans are now unscored. Stability ignores unscored rows and returns zero when no accepted rows exist.

### Workflow naming created a human-factors failure

The repository exposed both **Governed semantic plan model calibration** and **Governed final semantic plan model calibration**. The names differed by one word but represented materially different candidate sets and contract transformations. The wrong workflow was dispatched even though the final implementation was correct.

This was a repository UX defect, not a user error. The obsolete manual workflow is removed from the Actions UI by issue #271. Its runner, configuration, documentation and Git history remain available for audit.

### Too many incremental harnesses accumulated

Each discovery produced another runner or workflow. That was understandable during investigation, but it left overlapping concepts: semantic benchmark, model selection, model calibration and final model calibration.

The immediate cleanup removes obsolete workflow entry points. A future improvement should consolidate these behind one plan-driven runner with explicit checked-in modes rather than continuing to add workflow variants.

## Revised evaluation sequence

Future model evaluation should use this sequence:

```text
catalogue eligibility
→ representative route probe
→ one real full-contract smoke call
→ repeated single-case calibration
→ multi-case evaluation
→ reviewed decision
```

A candidate must not advance merely because a minimal route probe passed.

Before any paid job begins, the Actions summary should identify:

```text
plan identity
trusted main SHA
candidate models
case set
substantive call count
whole-run cost ceiling
request compatibility transforms
evidence transformations
excluded models
validator-gated scoring status
```

Only after those fields match the intended experiment should model outcomes be interpreted.

## Current decision boundary

At the time of this record:

- no model is approved for production or automatic report generation;
- GPT-5.6 Sol remains the benchmark-only candidate;
- Nex N2 Mini remains the affordable deployment candidate pending a fair corrected call;
- MiniMax M3 does not advance;
- North Mini Code remains catalogue-ineligible;
- automatic generation and publication remain disabled;
- issue #269 remains open;
- the next valid evidence must come from the workflow visibly named **Semantic plan calibration — GPT-5.6 + Nex only**.

A successful two-call calibration would establish compatibility, not complete model selection. Repeated multi-case evidence and a separately reviewed decision would still be required before any production recommendation.

## Carry-forward lesson

The strongest result of this work is not yet a winning model. It is a better understanding of how to evaluate models responsibly inside a governed delivery system.

Model evaluation is not only a question of prompt and benchmark quality. It is also a product and systems problem involving provider contracts, evidence semantics, cost envelopes, observability, workflow UX, failure classification and decision discipline. The harness must prove that it tested the intended experiment before the project is allowed to reason about which model performed best.
