# Final semantic claim-plan model calibration

Status: **superseded historical experiment; not dispatchable**.

Issue #269 proposed one final compatibility calibration for GPT-5.6 Sol and Nex N2 Mini. Run `29235513924` had identified two integration corrections: canonical cross-source price normalisation and a required user-role execution message for Nex. The later catalogue and prompt-v2 screens then exposed a broader architectural problem: the model was still expected to reproduce too many deterministic semantic rules while constructing a complete claim plan.

The calibration was prepared but was not run. It is superseded by Phase 6, which compiles valid claim candidates deterministically and permits a model only to select bounded candidate IDs.

- Phase 5 conclusion: [`../evaluation/phase-05/README.md`](../evaluation/phase-05/README.md)
- Corrective run evidence: [`../evaluation/phase-05/corrective-screen-29285569716.md`](../evaluation/phase-05/corrective-screen-29285569716.md)
- Phase 6 roadmap: [`../planning/roadmap/phase-06-deterministic-claim-selection.md`](../planning/roadmap/phase-06-deterministic-claim-selection.md)
- Parent Phase 6 issue: #283

## Historical scope

The prepared plan contained exactly two route probes and two substantive generations:

```text
GPT-5.6 Sol:  one route probe + one full-contract call
Nex N2 Mini: one route probe + one full-contract call
whole-run ceiling: USD 0.25
```

It used prompt `crypto-market-claim-plan/v2`, canonical Coinbase `price` to `price_usd` evidence normalisation, the bounded Nex user-role compatibility message and validator-gated scoring.

## Preserved evidence

The following remain source-controlled and auditable:

- `config/semantic-plan-model-final-calibration-v2.yml`;
- the prompt-v2 screen runner and supporting evaluation code;
- prompt v1 and v2 artefacts;
- canonical claim-plan schema, validator and renderer;
- this historical documentation;
- Git history and any retained protected artefacts from preceding runs.

Only the manual GitHub Actions workflow entry point is removed. Removing the workflow prevents accidental paid execution but does not erase the design or evidence trail.

## Decision boundary

- Do not dispatch the GPT-5.6 Sol/Nex full-plan calibration.
- Do not interpret the retained plan as an approved next experiment.
- No model was selected.
- Automatic generation and publication remain disabled.
- Any future model call must use the Phase 6 candidate-selection boundary and a separately reviewed issue, case plan and cost ceiling.
