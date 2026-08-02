# Slice 6 scoring and decision contract

This contract is fixed before protected model output exists. The reviewed useful
candidate IDs from Slice 3 are authoritative; no expectation may be added after a run.

## Candidate quality

For each logical run:

```text
precision = reviewed-useful selected / model-selected
recall    = reviewed-useful selected / reviewed-useful expected
F1        = harmonic mean of precision and recall
```

A first-pass or repaired accepted ID list receives model credit. A deterministic
fallback is represented as an empty model selection: it has zero selected candidates,
zero useful selections, zero precision and zero recall. The valid fallback plan is not
credited to the model.

Aggregate precision and recall are micro-averaged across all fifteen logical runs per
model. Every repeat contributes its full reviewed-useful denominator, including failed
or fallback runs.

## Stability

Each case has three repeats, producing three pairwise comparisons. Failed or fallback
runs contribute the empty set, so reliability failures reduce stability rather than
being silently excluded.

- pairwise stability is Jaccard similarity over model-selected candidate IDs;
- exact-repeat rate is the fraction of repeat pairs with identical selected sets;
- reported model stability is the mean of the five case-level pairwise means.

## Structural safety

The Slice 5 validator independently enforces exact membership, uniqueness, maximum
count, section and intent limits, evidence-bundle identity and one candidate per
redundancy group. The evaluator separately records prohibited candidate selections,
repair use, fallback reasons, actual model/provider identity and cost completeness.

Schema validity and deterministic rendering are safety gates, not editorial quality
points.

## Quality upper-bound gate

`openai/gpt-5.6-sol` must satisfy every condition:

- at least 14 of 15 runs accepted without deterministic fallback;
- zero prohibited selections;
- precision at least 79.285714%;
- recall at least 68.421053%;
- F1 at least 76.232877%;
- mean pairwise Jaccard at least 0.80;
- complete and compliant identity, routing, policy and cost evidence.

Failure yields `remove-model-selector-from-active-roadmap`.

## Deployment-candidate gate

Only after the quality upper bound passes, `nex-agi/nex-n2-mini` must satisfy every
condition:

- at least 14 of 15 runs accepted without deterministic fallback;
- zero prohibited selections;
- precision and recall each within two percentage points of the deterministic baseline;
- F1 at least 76.232877%;
- at least 80% of the GPT F1 uplift over baseline;
- mean pairwise Jaccard at least 0.80;
- p95 logical-run latency at most 30 seconds;
- mean model-call cost per accepted selection at most USD 0.02;
- complete and compliant identity, routing, policy and cost evidence.

Failure yields `research-only-no-deployment-selector`; success yields
`retain-bounded-selector-candidate`.

A catalogue, route, policy or infrastructure failure before a complete corpus yields
`inconclusive-infrastructure`. None of these outcomes enables production use. A
separate reviewed decision pull request is mandatory.
