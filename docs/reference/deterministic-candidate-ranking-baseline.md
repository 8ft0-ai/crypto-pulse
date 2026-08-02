# Deterministic candidate-ranking baseline

> **Mode:** Reference  
> **Audience:** CryptoPulse developers, reviewers and governance stakeholders  
> **Outcome:** Look up the permanent no-LLM ranking, selection, claim-plan reconstruction and rendering contract introduced by Phase 6 Slice 4.

## Canonical artefacts

| Artefact | Canonical path |
| --- | --- |
| Ranking configuration | [`config/claim-candidate-ranking-v1.yml`](../../config/claim-candidate-ranking-v1.yml) |
| Rank, select and reconstruct implementation | [`llm_analysis/deterministic_ranking.py`](../../llm_analysis/deterministic_ranking.py) |
| Corpus evaluator | [`llm_analysis/deterministic_baseline_evaluation.py`](../../llm_analysis/deterministic_baseline_evaluation.py) |
| Retained-record projection | [`llm_analysis/deterministic_baseline_record.py`](../../llm_analysis/deterministic_baseline_record.py) |
| Evaluation summary | [`evaluation/phase-06/deterministic-baseline/summary.json`](../../evaluation/phase-06/deterministic-baseline/summary.json) |
| Selected score records | [`evaluation/phase-06/deterministic-baseline/scores.json`](../../evaluation/phase-06/deterministic-baseline/scores.json) |
| Reviewer report | [`evaluation/phase-06/deterministic-baseline/review.md`](../../evaluation/phase-06/deterministic-baseline/review.md) |
| Reviewed candidate corpus | [`evaluation/phase-06/claim-candidate-gold/manifest.yml`](../../evaluation/phase-06/claim-candidate-gold/manifest.yml) |
| Existing claim-plan schema | [`schemas/crypto-market-claim-plan-v1.json`](../../schemas/crypto-market-claim-plan-v1.json) |

The baseline implements Phase 6 Slice 4 under issue #291. It consumes the candidate contract from Slice 1, compiler output from Slice 2 and reviewed useful expectations from Slice 3. It does not change those earlier contracts.

## Purpose

The deterministic compiler can produce between 201 and 230 valid candidates for the five frozen evaluation cases. A report cannot use all of them. The ranking baseline reduces that complete valid set to seven non-redundant claims, reconstructs the existing canonical claim plan, validates it and renders it without an LLM.

This path has three permanent roles:

1. provide a complete report path when no provider secret exists;
2. remain the fallback if a later optional model selector fails;
3. provide the fixed comparator for measuring whether model selection adds value.

The baseline is not a production scheduler or publisher. It creates no pull request, changes no report source and writes no generated site output.

## Version

```text
phase-06-deterministic-ranking/v1
```

The ranking version appears in the source-controlled configuration and every selection result. Changes to scoring, required slots, bounds or tie-breaking require a new reviewed change and refreshed retained evaluation artefacts.

## Input contract

The baseline receives:

- one schema-valid `crypto-market-evidence-bundle/v1` object;
- the complete candidate set compiled for that exact bundle;
- the versioned ranking configuration;
- the existing evidence, candidate and claim-plan schemas.

Every candidate must:

- pass the candidate schema;
- carry the supplied evidence-bundle ID;
- have an exact content-derived candidate ID;
- be unique within the input set.

The baseline rejects empty candidate sets, mismatched bundles, stale candidate IDs and duplicate IDs. It never silently repairs or deduplicates input.

## Ranking policy

Ranking is lexicographic. It is not an opaque weighted sum. The configured score vector is evaluated from left to right, with larger values preferred:

| Position | Dimension | Purpose |
| ---: | --- | --- |
| 1 | Conflict status | Prefer explicit divergence, then corroboration. |
| 2 | Quality significance | Prefer material limitations before minor or non-quality facts. |
| 3 | Materiality | Prefer high, then medium and low market movement. |
| 4 | Comparison relation | Prefer divergence and opposite-direction relations before routine inequalities. |
| 5 | Metric | Prefer canonical price and relevant movement horizons. |
| 6 | Evidence scope | Prefer primary-market evidence, then exchange and governance evidence. |
| 7 | Subject diversity | Prefer a subject not yet represented after higher-priority signals tie. |
| 8 | Intent | Apply the explicit intent preference. |
| 9 | Cross-source evidence | Prefer cross-source support when earlier dimensions tie. |
| 10 | Corroboration count | Prefer more independent named sources within the bounded count. |
| 11 | Recency | Use the candidate recency bucket; `unknown` remains neutral and deterministic. |

The score vector contains integers only. No wall-clock value, random value, provider result or traversal position is used.

After the vector, ties are resolved using the canonical candidate sort key and then the candidate ID. Equivalent candidate inputs therefore have one stable result.

## Required editorial slots

Before general ranked fill, the baseline attempts to fill these source-controlled slots when matching candidates exist:

| Slot | Required semantics |
| --- | --- |
| Primary market price | One canonical `price_usd` absolute observation from primary-market evidence. |
| Daily market movement | One primary-market `change_24h_pct` or `change_1d_pct` directional claim. |
| Primary market price comparison | One compatible primary-market `price_usd` comparison. |
| Primary market movement comparison | One compatible primary-market 24-hour or one-hour movement comparison. |
| Explicit data-quality limitation | One repository-valid governance limitation. |
| Snapshot status | One bounded snapshot status claim. |

The slots prevent large mechanically valid candidate groups from displacing the representative claims needed for a usable report. They constrain selection only; they do not create candidates or change candidate meaning.

A divergent conflict or material quality signal may then receive explicit coverage if capacity and redundancy constraints permit. Remaining capacity is filled by the same deterministic score vector.

## Hard selection bounds

The version-1 policy enforces:

```text
maximum selected candidates: 7
maximum claims in one section: 8
one candidate per redundancy group
```

The configured section limits are:

| Section | Limit |
| --- | ---: |
| `market_summary` | 1 |
| `key_observations` | 4 |
| `risks_and_limitations` | 0 |
| `data_quality` | 2 |
| `source_status` | 0 |

The configured intent limits are:

| Intent | Limit |
| --- | ---: |
| `absolute_observation` | 1 |
| `directional_observation` | 3 |
| `comparison` | 2 |
| `source_status` | 0 |
| `data_quality_limitation` | 1 |
| `snapshot_status` | 1 |

Routine healthy source-status claims remain valid compiler candidates but do not consume capacity in this compact baseline. Snapshot status remains included alongside explicit quality limitations because it records the overall governed bundle state.

Malformed or impossible bounds fail closed during configuration loading. The claim-plan schema remains an independent maximum-cardinality defence.

## Selection record

The selector records:

- ranking version and configuration hash;
- evidence-bundle identity;
- complete candidate count and ordered-set hash;
- selected candidate IDs in deterministic selection order;
- score vector and selection stage for every selected candidate;
- section and intent counts;
- distinct subject count;
- unique redundancy-group count.

Only IDs already present in the supplied candidate set may be selected. Duplicate selected IDs and repeated redundancy groups are rejected.

## Canonical plan reconstruction

The model does not participate in reconstruction. For each selected candidate, repository code copies exactly:

```text
intent
evidence_ids
comparison_relation
confidence
```

The candidate section becomes the claim-plan section. Candidate-only metadata such as features, metric, subject and score vector is not copied into the plan.

A stable claim ID is derived from the candidate digest:

```text
claim-candidate:sha256:<64 hex characters>
    -> claim-<64 hex characters>
```

The plan uses the existing:

```text
crypto-market-claim-plan/v1
```

contract and canonical section order. Unknown IDs, duplicate selections, unsupported sections and claim-ID collisions fail closed.

## Validation and rendering gate

A reconstructed plan is not accepted merely because selection completed. The baseline passes it through the existing `validate_claim_plan` pipeline, including:

- schema validation;
- evidence-bundle identity and evidence-reference checks;
- section and claim-order checks;
- intent and comparison semantics;
- source-status, snapshot-status and data-quality eligibility;
- unsafe untrusted evidence policy checks.

Only a validator-accepted plan reaches `render_claim_plan`. The renderer owns exact values, units, labels, dates and Markdown. Ranking code does not author prose.

## Retained evaluation

The baseline is evaluated over the same five frozen cases as the reviewed gold candidate corpus:

| Case | Candidates | Selected | Gold-useful selected | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| `historical-degraded-sparse` | 201 | 7 | 5 | 71.43% | 62.50% |
| `historical-normal-crosschecked` | 230 | 7 | 6 | 85.71% | 60.00% |
| `historical-material-move` | 230 | 7 | 6 | 85.71% | 75.00% |
| `adversarial-prompt-injection` | 230 | 7 | 5 | 71.43% | 83.33% |
| `adversarial-source-disagreement` | 230 | 7 | 4 | 57.14% | 66.67% |

Overall:

```text
selected claims:             35
reviewed-useful selections:  26
selected-useful precision:   74.29%
selected-useful recall:      68.42%
validated plans:              5 / 5
rendered reports:             5 / 5
candidate permutations:       5 / 5 stable
 evidence permutations:       5 / 5 stable
provider calls:               0
```

Precision and recall are descriptive editorial measures against the reviewed Slice 3 subset. They are not structural validity gates and do not imply that every mechanically valid candidate omitted from the gold subset is wrong. Later model selection must receive the same candidate sets and demonstrate measurable incremental value over these retained results.

## Determinism checks

For every case, the evaluator runs the baseline three ways:

1. canonical candidate and evidence order;
2. reversed candidate input order;
3. reversed evidence input order followed by recompilation.

It byte-compares:

- the complete selection record;
- the reconstructed claim plan;
- rendered Markdown.

All five cases pass both permutation comparisons. The retained summary records candidate-set, selection, plan and Markdown hashes for independent review.

## Prompt-injection boundary

The adversarial prompt-injection case retains its `evaluation-only` classification. Unsafe instruction-like source detail was already excluded by the compiler and cannot enter the selected plan or rendered report. Ranking consumes candidate metadata and IDs, not free-form instructions.

Tests assert that the retained selection, score record and reviewer report contain none of the injected instruction or trading-recommendation text.

## Reproduce or check the retained record

Write the current deterministic outputs:

```bash
python -m llm_analysis.deterministic_baseline_record
```

Verify the checked-in files without changing them:

```bash
python -m llm_analysis.deterministic_baseline_record --check
```

The check recomputes the frozen corpus, complete candidate sets, selections, reconstructed plans and rendered Markdown. It fails if `summary.json`, `scores.json` or `review.md` differs by one byte.

## Failure behaviour

Stable errors are raised for conditions including:

- missing or unsupported ranking configuration;
- unsafe or impossible bounds;
- unknown feature, scope or relation values;
- empty candidate input;
- invalid candidate schema or identity;
- candidate/evidence bundle mismatch;
- duplicate or unknown selected IDs;
- repeated redundancy groups;
- required coverage made impossible by configured bounds;
- invalid reconstructed plan;
- selection, plan or rendering permutation drift;
- retained-output drift.

The baseline does not retry with weaker rules, substitute another candidate set, call a model or publish partial output.

## Responsibility boundary

| Responsibility | Owner |
| --- | --- |
| Evidence collection and normalisation | Existing repository pipeline |
| Valid candidate enumeration | Deterministic compiler |
| Score dimensions and editorial slots | Versioned ranking configuration |
| Ranking, bounds and redundancy | Deterministic baseline |
| Candidate meaning | Candidate contract; unchanged during selection |
| Claim-plan reconstruction | Deterministic baseline |
| Plan acceptance | Existing fail-closed validator |
| Exact values and prose | Existing deterministic renderer |
| Model/provider calls | None |
| Scheduling and publication | Outside this slice and separately governed |

## Later model-selection boundary

Slice 5 may optionally replace only the selected candidate ID sequence. It must not replace candidate compilation, alter claim semantics or remove this baseline.

Any model selector must:

- receive the same valid candidate set;
- return candidate IDs only;
- pass exact-ID, uniqueness, cardinality and redundancy validation;
- fall back to this deterministic baseline on failure;
- be compared against the retained precision, recall, redundancy, stability, latency and cost record.

Automatic generation and publication remain disabled.
