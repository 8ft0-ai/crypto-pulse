# Phase 6 bounded candidate-selection model comparison

Status: completed historical evaluation.  
Comparison issue: #295  
Corrective issue: #300  
Final decision: `planning/roadmap/phase-06-bounded-selector-comparison-decision.md`

This directory documents the protected Slice 6 comparison. The paid workflow entry point
was removed after the final reviewed decision. No provider output is committed here;
protected outputs remain referenced by their GitHub Actions artifact identities.

## Fixed comparison

| Role | Exact model | Actual provider | Cases | Repeats | Output cap |
| --- | --- | --- | ---: | ---: | ---: |
| Quality upper bound | `openai/gpt-5.6-sol` | `OpenAI` | 5 | 3 | 1,024 |
| Deployment candidate | `nex-agi/nex-n2-mini` | `Nex AGI` | 5 | 3 | 512 |

The deterministic Slice 4 selector was regenerated from the same candidate sets and
remains the permanent comparator and sole active selector. Deterministic fallback kept
final plans valid but gave a failed model run zero quality credit.

## Compact transport

The complete canonical request and candidate set remain repository-owned. The provider
transport projected every full candidate ID plus bounded editorial fields into a compact
positional catalogue. It omitted evidence IDs, source prose and verbose repeated property
names without removing candidates or weakening repository validation.

Secret-free preparation proved the ordered ID set and kept each compact request below
65,536 bytes. Frozen request sizes ranged from 45,174 to 51,320 bytes for 201–230
candidates, compared with 125,714 to 142,678 bytes for the canonical requests.

## Deterministic baseline

```text
Selected candidates:        35
Reviewed-useful selected:   26
Reviewed-useful expected:   38
Precision:                  74.285714%
Recall:                     68.421053%
F1:                         71.232877%
Validated plans:            5 / 5
Rendered reports:           5 / 5
Provider calls:             0
```

## Protected attempt 1

Run `30771922641` validated the exact GPT/OpenAI route. The first full-catalogue corpus
call then used 35,806 input tokens, exhausted the 512-token output allowance and cost
USD 0.23914375 against the fixed USD 0.12 per-call ceiling. The metered response was
retained before abort. No second corpus call and no Nex call occurred.

```text
Classification: inconclusive-infrastructure
Protected artifact: 8840792374
Digest: sha256:a0c4d542d6fdfac5cc03a1167aca62da9ab675f40dd7b91618932571f70a3629
```

## Corrective calibration

PR #301 retained the complete candidate catalogue while adding the compact transport,
raising the GPT output cap to 1,024, setting a USD 0.15 per-call ceiling and adding
decisive stopping after two fully metered model fallbacks. It did not introduce a
shortlist, post-hoc gold filtering, provider substitution, a third model or production
enablement.

## Protected attempt 2 — final run

Run `30777564268` at trusted SHA
`40c9fd533dd79bb4b4a6c8bd1f232646bf1f37c5` passed the one-time guard, secret-free
preparation and exact GPT/OpenAI route probe.

Three complete GPT repeats were retained for `historical-degraded-sparse`:

| Repeat | Outcome | Precision | Recall | F1 | Cost |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | Accepted initial | 28.57% | 25.00% | 26.67% | USD 0.1424575 |
| 2 | Deterministic fallback | 0% | 0% | 0% | USD 0.040352 |
| 3 | Accepted initial | 42.86% | 37.50% | 40.00% | USD 0.033482 |

The next exact-route call returned a complete seven-ID envelope but cost USD 0.15841625
against the fixed USD 0.15 ceiling. The metered response was retained before abort. No
later GPT call and no Nex call occurred. Total reported final-run spend was USD
0.37542275.

```text
Classification: inconclusive-infrastructure
Prepared artifact: 8842553997
Prepared digest: sha256:6b39ca56a84bbdc3dcd63e438fce0b5401e75da95dbeae3c5a3a46f108c72204
Protected artifact: 8842583436
Protected digest: sha256:a40c94efcc7c125026abfc69d942eeb7ae70e210f81c366b4319dcecab7e54c7
```

The three scored rows are incomplete diagnostic evidence only. They cover one case,
include one fallback and do not adjudicate the predeclared Gate A aggregate rule. No Nex
quality, stability, latency or deployment conclusion is claimed.

## Final decision

Both protected attempts are classified as `inconclusive-infrastructure` because neither
fixed corpus completed. Separately, the reviewed roadmap decision removes bounded model
selection from the active roadmap and retains deterministic selection as the only
supported active path.

No further paid Phase 6 run is authorised. The manual workflow entry point is archived.
Configuration, prompts, schemas, compact projection, runners, scoring code, tests,
documentation, Git history and artifact references remain auditable.

## Reproduce secret-free preparation

The preparation path remains available for historical verification and makes no provider
call:

```bash
python -m llm_analysis.candidate_selection_model_comparison_runner prepare \
  --repository-root . \
  --config config/candidate-selection-model-comparison.yml \
  --output-dir /tmp/candidate-selection-model-comparison-prepared
```

Do not use the retained runner to initiate another Phase 6 provider evaluation. A future
model-selector investigation requires a new phase, reviewed evidence plan, budget,
stop-loss and explicit authority.
