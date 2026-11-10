# Slice 6 scoring and decision contract

This contract is fixed before the corrective protected run. The reviewed useful
candidate IDs from Slice 3 are authoritative; no expectation may be added after a run.

## Candidate quality

For each logical run:

```text
precision = reviewed-useful selected / model-selected
recall    = reviewed-useful selected / reviewed-useful expected
F1        = harmonic mean of precision and recall
```

A first-pass or repaired accepted ID list receives model credit. A deterministic
fallback is represented as an empty model selection: zero selected candidates, zero
useful selections, zero precision and zero recall. The valid fallback plan is not
credited to the model.

Aggregate precision and recall are micro-averaged across all executed logical runs.
For a complete model corpus, all fifteen repeats contribute their full reviewed-useful
denominator. A decisive two-fallback stop is evaluated through the acceptance gate
rather than extrapolating unexecuted quality scores.

## Stability

Each completed case has three repeats and three pairwise comparisons. Failed or fallback
runs contribute the empty set, so reliability failures reduce stability rather than
being excluded.

- pairwise stability is Jaccard similarity over model-selected candidate IDs;
- exact-repeat rate is the fraction of repeat pairs with identical selected sets;
- complete-model stability is the mean of the five case-level pairwise means.

## Structural safety

The compact request changes provider transport only. It preserves the exact ordered
full candidate-ID set. Slice 5 independently validates membership, uniqueness, maximum
count, section and intent limits, bundle identity and redundancy groups against the
complete canonical candidate set.

Schema validity and deterministic rendering are safety gates, not editorial quality
points. Provider/model identity, routing, metering and cost completeness are governance
gates.

## Quality upper-bound gate

`openai/gpt-5.6-sol` must satisfy every condition:

- at least 14 of 15 runs accepted without deterministic fallback;
- zero prohibited selections;
- precision at least 79.285714%;
- recall at least 68.421053%;
- F1 at least 76.232877%;
- mean pairwise Jaccard at least 0.80;
- complete and compliant identity, routing, policy and cost evidence.

After two fully metered model fallbacks, at most 13 runs can be accepted. The comparison
therefore stops immediately, skips Nex and yields
`remove-model-selector-from-active-roadmap`.

An infrastructure, catalogue, route, identity, policy or metering failure does not count
as a model fallback and remains `inconclusive-infrastructure`.

## Deployment-candidate gate

Only after the quality upper bound completes and passes, `nex-agi/nex-n2-mini` must
satisfy every condition:

- at least 14 of 15 runs accepted without deterministic fallback;
- zero prohibited selections;
- precision and recall each within two percentage points of the deterministic baseline;
- F1 at least 76.232877%;
- at least 80% of the GPT F1 uplift over baseline;
- mean pairwise Jaccard at least 0.80;
- p95 logical-run latency at most 30 seconds;
- mean model-call cost per accepted selection at most USD 0.02;
- complete and compliant identity, routing, policy and cost evidence.

Two fully metered Nex fallbacks are a decisive acceptance failure and yield
`research-only-no-deployment-selector`. A complete passing gate yields
`retain-bounded-selector-candidate`.

## Cost and execution bounds

```text
Route probes:                              2 maximum
Logical selector runs:                    30 maximum
Substantive calls:                        60 maximum
Semantic repairs per run:                  1 maximum
Model fallbacks before decisive failure:   2
Whole-run cost:                         USD 5.00 maximum
```

| Model | Per-call | Per-model | Output cap |
| --- | ---: | ---: | ---: |
| GPT-5.6 Sol | USD 0.15 | USD 4.51 | 1,024 |
| Nex N2 Mini | USD 0.01 | USD 0.31 | 512 |

These are maxima, not minimum call counts. Early stopping reduces calls and cost.
Missing cost evidence reserves the full per-call ceiling and produces
`inconclusive-infrastructure`.

None of the outcomes enables production use. A separate reviewed decision pull request
is mandatory.
