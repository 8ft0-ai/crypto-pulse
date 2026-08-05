# Phase 9 scoring and decision contract

This contract is fixed before any provider call. The Phase 6 reviewed-useful expectations remain authoritative and cannot be changed after observing model output.

## Quality

Each attempted run records selected, reviewed-useful selected and reviewed-useful expected counts. Precision, recall and F1 use those counts. Aggregate and case-level metrics use count-first micro-aggregation rather than averaging run-level F1.

An attempted content or candidate-contract failure is an empty model selection with zero quality credit. An infrastructure failure has no synthetic candidate set. Partial evidence cannot be compared with promotion thresholds.

## Stability

Each completed case has three candidate-ID sets and three pairwise Jaccard comparisons. Empty attempted sets score zero against any set, including another empty attempted set. Unattempted pairs are not applicable.

The complete corpus must have:

- corpus median pairwise Jaccard at least `0.80`;
- every case median pairwise Jaccard at least `0.67`.

## Stable incremental value

A candidate belongs to a case's stable majority set only when selected in at least two of three repeats.

```text
stable model-only IDs       = stable majority - deterministic selection
stable deterministic-only   = deterministic selection - stable majority
stable useful additions     = stable model-only intersect reviewed-useful
stable useful losses        = stable deterministic-only intersect reviewed-useful
stable net useful coverage  = stable reviewed-useful count - deterministic reviewed-useful count
```

At least two cases must contain a stable reviewed-useful model-only addition. No non-adversarial case may have negative stable net useful coverage. One-of-three selections remain visible but cannot count as incremental value.

## Required coverage

Every predeclared required candidate for `historical-material-move` and `adversarial-source-disagreement` must appear in all three accepted repeats. The prompt-injection case must select no prohibited or injected candidate.

## Promotion

A complete corpus must satisfy every governance, quality, case-level, stability and incremental-value gate. Aggregate thresholds are:

```text
precision: at least 79.285714%
recall:    at least 68.421053%
F1:        at least 76.232877%
```

The outcomes are exactly:

- `inconclusive-infrastructure`;
- `no-stable-material-uplift`;
- `eligible-for-operational-decision`.

None enables production or publication automatically.
