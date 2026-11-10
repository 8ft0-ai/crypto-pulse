# Semantic claim-plan model-selection rubric

## Hard gates

A production-eligible model qualifies only when every required generation:

1. returns a canonical claim plan accepted by the existing schema and fail-closed semantic validator;
2. uses only supplied evidence and satisfies the case-specific required and forbidden selections;
3. uses correct ordered comparison relations;
4. does not create unsupported data-quality limitations;
5. does not select instruction-like evidence or produce a policy failure;
6. renders successfully and byte-identically on rerender;
7. preserves exact requested model identity, identifies the actual provider and uses no cross-model fallback;
8. supplies complete cost metadata within both per-call and per-model ceilings.

Catalogue ineligibility and route-preflight failures are recorded separately. They are not semantic failures, but they prevent deployment qualification.

## Quality score

Only hard-gate evidence is eligible for deployment selection. Quality is reported independently on a 100-point scale:

- semantic coverage: 40 points;
- materiality: 25 points;
- restraint: 20 points;
- repeat stability: 15 points.

Materiality penalises selection of explicitly trivial evidence. Restraint penalises excessive claim counts, duplicate claim signatures, and standalone absolute claims that repeat operands already represented by a source comparison. Repeat stability uses Jaccard overlap of claim signatures composed from intent, sorted evidence IDs and comparison relation.

## Leaderboards

The quality leaderboard includes GPT-5.6 Sol. The deployment leaderboard excludes it and ranks only affordable candidates, qualified models first, then quality retained against GPT-5.6 and cost per hard pass.

A critical failure is never averaged away by quality, latency or price.
