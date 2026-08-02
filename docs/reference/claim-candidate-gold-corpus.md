# Reviewed claim-candidate gold corpus

> **Mode:** Reference  
> **Audience:** CryptoPulse developers, reviewers and governance stakeholders  
> **Outcome:** Look up how Phase 6 measures deterministic candidate recall, invalid-combination absence and output stability before ranking begins.

## Canonical artefacts

| Artefact | Canonical path |
| --- | --- |
| Gold manifest | [`evaluation/phase-06/claim-candidate-gold/manifest.yml`](../../evaluation/phase-06/claim-candidate-gold/manifest.yml) |
| Per-case reviewed expectations | [`evaluation/phase-06/claim-candidate-gold/cases/`](../../evaluation/phase-06/claim-candidate-gold/cases/) |
| Normalisation probe | [`evaluation/phase-06/claim-candidate-gold/normalisation-probe.yml`](../../evaluation/phase-06/claim-candidate-gold/normalisation-probe.yml) |
| Machine summary | [`evaluation/phase-06/claim-candidate-gold/summary.json`](../../evaluation/phase-06/claim-candidate-gold/summary.json) |
| Reviewer report | [`evaluation/phase-06/claim-candidate-gold/review.md`](../../evaluation/phase-06/claim-candidate-gold/review.md) |
| Deterministic evaluator | [`llm_analysis/claim_candidate_gold_corpus.py`](../../llm_analysis/claim_candidate_gold_corpus.py) |
| Frozen Phase 5 corpus | [`evaluation/phase-05/corpus.yml`](../../evaluation/phase-05/corpus.yml) |
| Candidate compiler | [`llm_analysis/claim_candidate_compiler.py`](../../llm_analysis/claim_candidate_compiler.py) |

The corpus implements Phase 6 Slice 3 under issue #289. Candidate shape, identity and ordering remain governed by Slice 1. Candidate eligibility and compilation remain governed by Slice 2.

## Purpose

The compiler can produce hundreds of structurally valid candidates from one evidence bundle. The gold corpus does not declare every mechanically valid candidate equally useful. It records a reviewed subset that later ranking and selection work must have available, while separately locking the complete compiler count and ordered-set digest.

The corpus answers four questions:

1. Did the compiler produce every reviewed useful candidate?
2. Did it avoid specified invalid or misleading combinations?
3. Did candidate identity and order remain byte-stable?
4. What happens when cross-source price evidence is normalised explicitly rather than silently?

It does not answer which candidates should be selected for a final report. That begins in Slice 4.

## Frozen source cases

The manifest reuses the five cases in `evaluation/phase-05/corpus.yml` without modifying that file:

| Case | Classification | Purpose |
| --- | --- | --- |
| `historical-degraded-sparse` | `historical` | Required market evidence with degraded optional exchange coverage. |
| `historical-normal-crosschecked` | `historical` | Normal valid snapshot with Coinbase cross-check evidence. |
| `historical-material-move` | `historical` | Material directional movement over different time horizons. |
| `adversarial-prompt-injection` | `evaluation-only` | Unsafe instruction-like source detail derived from the normal snapshot. |
| `adversarial-source-disagreement` | `evaluation-only` | Deterministically changed Coinbase price derived from the normal snapshot. |

The evaluator verifies classification against the original Phase 5 scenario tags. A case tagged `evaluation-only` cannot be represented as historical, and a historical case cannot be relabelled as evaluation-only.

## Phase 5 immutability boundary

The Slice 3 manifest records the Git blob SHA of the Phase 5 corpus:

```text
1ebbda1bdc2acf7a0b4eaca3c8f88cc98f523556
```

The evaluator recalculates the Git blob identity from the file bytes before preparing cases. Any byte change, including an otherwise harmless whitespace edit, fails with `corpus_blob_mismatch`.

Historical snapshots are still validated through the existing Phase 5 preparation path. Their configured SHA-256 and expected quality status therefore remain enforced by the original evaluator.

## Reviewed expectation format

Each case file records:

- `classification`;
- expected complete candidate count;
- expected SHA-256 of the canonically ordered candidate array;
- reviewed useful candidate signatures;
- forbidden predicates and text;
- deliberate omissions with rationale.

A useful candidate signature is repository-owned semantics, not prose:

```yaml
match:
  intent: directional_observation
  metric: change_24h_pct
  comparison_relation: none
  evidence_ids:
  - market.asset.solana.change_24h_pct
```

Every signature must resolve to exactly one compiled candidate. Zero matches represent missing recall. Multiple matches represent an ambiguous gold record. Both fail closed.

Candidate IDs are not hand-authored in the case files. They are resolved from the reviewed semantic signatures and written to the generated summary and reviewer report.

## Recall

For one case:

```text
candidate recall = resolved reviewed useful candidates / reviewed useful candidates
```

Slice 3 requires 100% recall for every case and overall. The reviewed result is:

```text
38 / 38 useful expectations resolved
```

This is a recall measure over reviewed useful candidates. It is not precision over all compiler output and does not assert that all 1,121 raw candidates should appear in a report.

## Complete output identity

For each case, the evaluator records:

- complete candidate count;
- SHA-256 of the complete canonically ordered candidate array;
- successful byte comparison after reversing evidence traversal order.

Current reviewed values are:

| Case | Candidates | Ordered candidate SHA-256 |
| --- | ---: | --- |
| `historical-degraded-sparse` | 201 | `330769db9e7f13663bdd34ccaa49bbfa73cc7cda832196072e252df82ef9eaf6` |
| `historical-normal-crosschecked` | 230 | `0e3fba876a8fc81f61dd567e7536cc281d59addc55961bd81b3a928d406c8f4c` |
| `historical-material-move` | 230 | `4ec53cafdd4399dd910f2eab56a1c064fbe65f1857110c8f4ac4288d450037d0` |
| `adversarial-prompt-injection` | 230 | `7624f118789d912e886c836198ae65bae032929a8bd506a86b6b8e71e674be4b` |
| `adversarial-source-disagreement` | 230 | `e0d0199fecb9c33e07662cd5074e0629bc9877cc8fb409cfd486d36ccef86ce6` |

A compiler change that alters count, identity or ordering must be reviewed by updating the relevant gold record. The evaluator never rewrites gold expectations automatically.

## Prohibited combinations

Case files can assert bounded absence predicates:

### `evidence_ids_together`

Fails when one candidate cites all listed evidence IDs. This proves, for example, that raw Coinbase `price` is not silently combined with CoinGecko `price_usd`.

### `evidence_id_referenced`

Fails when any candidate cites the specified evidence record. The prompt-injection case uses this to prove that unsafe `source.binance.reason` text cannot enter candidate semantics.

### `candidate_match`

Fails when a candidate matches a partial semantic signature. The normal case uses this to prove that `valid-ok` snapshot status does not become a data-quality limitation.

### `mixed_source_status`

Fails when a `source_status` candidate cites records from more than one source subject.

### `comparison_field_or_unit_mismatch`

Fails when a comparison cites operands whose fields or units differ.

Case files can also prohibit literal text from the complete canonical candidate JSON. The reviewed corpus currently performs 20 prohibited checks with zero matches.

## Deliberate omissions

Each case records omissions separately from failures. An omission explains why an intuitively attractive claim is not expected from the current governed evidence.

Examples include:

- no exchange comparison when the degraded case contains no exchange row;
- no limitation for a healthy snapshot;
- no comparison between Ethereum seven-day movement and Solana 24-hour movement;
- no prompt-injection detail in candidate output;
- no raw cross-source disagreement before explicit measure normalisation.

Omissions are reviewer-visible decisions. They are not silently treated as compiler defects.

## Explicit cross-source normalisation probe

Raw governed evidence contains:

```text
exchange.coinbase_exchange.btc-usd.price
market.asset.bitcoin.price_usd
```

The field and subject representations differ, so Slice 2 correctly does not compare them.

Slice 3 includes a separate evaluation-only probe. It performs an explicit evidence transformation:

```text
exchange.coinbase_exchange.btc-usd.price
    -> exchange.coinbase_exchange.bitcoin.price_usd
```

The transformed record uses the canonical Bitcoin asset subject and `price_usd` field. The complete bundle is then rehashed before compilation.

Reviewed identities are:

```text
previous bundle: sha256:7ad5c0cb63467b430f831b4da1cc8406626c792c04cf579e87e1757cc1331da1
new bundle:      sha256:a5358ca532515f3ed3349c603b978ee986b54b5a608854131af44efd539b1862
```

The transformed bundle produces 241 candidates with ordered digest:

```text
fd2e3784a476a98ba3305b5579c1b076543cf3a46d027fcdbb31c92d8346a2df
```

The expected cross-source candidate is:

```text
claim-candidate:sha256:066f8703cf8e4204a7a35fc74f15d136ad3d17b326770116e6c1dbc160ce3497
```

It has relation `not_equal`, `cross_source: true`, `conflict_status: divergent` and `corroboration_count: 2`.

The probe is evidence about a possible future normalisation contract. It is not a historical fact, report input or compiler repair rule.

## Generated outputs

The evaluator produces two checked-in artefacts:

```text
evaluation/phase-06/claim-candidate-gold/summary.json
evaluation/phase-06/claim-candidate-gold/review.md
```

`summary.json` is canonical JSON containing counts, identities, recall, resolved candidate IDs and probe evidence. `review.md` is the human-readable rendering of the same evaluation.

CI recomputes both and compares their bytes. Manual edits or stale outputs fail with `generated_output_drift`.

## API

```python
result = evaluate_claim_candidate_gold_corpus(repository_root)
```

The returned `ClaimCandidateGoldCorpusEvaluation` contains:

```text
summary
summary_bytes
report_markdown
```

The command-line interface can write or check the retained outputs:

```bash
python -m llm_analysis.claim_candidate_gold_corpus
python -m llm_analysis.claim_candidate_gold_corpus --check
```

## Fail-closed errors

`ClaimCandidateGoldCorpusError` exposes stable fields:

```text
code
path
message
```

Compilation or evaluation fails for conditions including:

- malformed manifest, case or probe records;
- missing or unsafe repository-relative paths;
- Phase 5 corpus byte drift;
- case order or classification drift;
- candidate count or ordered-set hash drift;
- useful expectations resolving zero or multiple times;
- prohibited candidate or text matches;
- evidence traversal changing candidate bytes;
- normalisation failing to create a new bundle identity;
- normalisation candidate or feature mismatch;
- generated summary or report drift.

No record is repaired or refreshed automatically.

## Scope boundary

The gold-corpus evaluator performs no:

- ranking or candidate selection;
- production candidate-to-plan reconstruction;
- model prompt or provider request;
- paid evaluation;
- automatic report generation or publication;
- mutation of the frozen Phase 5 corpus or historical snapshots;
- modification of the Slice 1 candidate contract or Slice 2 compiler.

Slice 4 may use the reviewed corpus to evaluate a deterministic ranking baseline. It must not reinterpret evaluation-only cases as market facts.
