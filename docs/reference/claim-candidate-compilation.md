# Deterministic claim-candidate compilation

> **Mode:** Reference  
> **Audience:** CryptoPulse developers, reviewers and governance stakeholders  
> **Outcome:** Look up how canonical evidence becomes a complete, deterministic set of repository-owned claim candidates.

## Canonical artefacts

| Artefact | Canonical path |
| --- | --- |
| Candidate compiler | [`llm_analysis/claim_candidate_compiler.py`](../../llm_analysis/claim_candidate_compiler.py) |
| Candidate schema | [`schemas/crypto-market-claim-candidate-v1.json`](../../schemas/crypto-market-claim-candidate-v1.json) |
| Evidence schema | [`schemas/crypto-market-evidence-bundle-v1.json`](../../schemas/crypto-market-evidence-bundle-v1.json) |
| Candidate identity and ordering | [`llm_analysis/claim_candidate_contract.py`](../../llm_analysis/claim_candidate_contract.py) |
| Existing semantic validator | [`llm_analysis/claim_plan_validation.py`](../../llm_analysis/claim_plan_validation.py) |
| Existing deterministic renderer | [`llm_analysis/claim_plan_render.py`](../../llm_analysis/claim_plan_render.py) |

The compiler implements Phase 6 Slice 2 under issue #287. The candidate object, identity algorithm and ordering contract remain defined by Slice 1 in [Deterministic claim-candidate contract](claim-candidate-contract.md).

## API

```python
compile_claim_candidates(
    bundle,
    evidence_schema=evidence_schema,
    candidate_schema=candidate_schema,
)
```

The result is an immutable tuple of candidate dictionaries in canonical candidate order.

The caller supplies the canonical evidence and candidate schemas. Compilation fails before semantic use when the evidence bundle does not satisfy its schema.

## Pipeline boundary

```text
canonical evidence bundle
        ↓
schema validation
        ↓
explicit candidate eligibility rules
        ↓
repository-owned semantic candidate construction
        ↓
content-derived candidate IDs
        ↓
exact-ID and duplicate validation
        ↓
candidate-schema validation
        ↓
canonical candidate ordering
```

The compiler does not rank candidates, choose a subset, reconstruct a production claim plan, call a provider or render a report.

## Candidate subject keys

Evidence subject IDs are intentionally broad. A validated evidence record may contain an ID that starts with a digit or includes upper-case or display-oriented characters. Candidate subject IDs use the stricter repository-key pattern defined by Slice 1.

The compiler applies one explicit metadata projection:

1. a lower-case evidence subject ID that already satisfies the candidate pattern is preserved unchanged;
2. any broader ID becomes a type-prefixed lower-case slug;
3. a 12-character canonical SHA-256 suffix derived from the original subject type and ID is appended.

For example, an evidence snapshot ID such as:

```text
1742-aest
```

becomes a candidate metadata key shaped like:

```text
snapshot_1742_aest_<hash>
```

This projection does not mutate the evidence bundle, evidence IDs, operands, field, unit, value or source. Evidence references remain authoritative. The hash suffix prevents two distinct broad evidence IDs from silently collapsing to the same candidate subject key.

## Absolute observations

One absolute candidate is emitted for each eligible repository-renderable market observation.

Eligible evidence types are:

```text
number
timestamp
boolean
set
status
```

The subject must be one of:

```text
asset
market
exchange_pair
defi_metric
```

The evidence must have a repository-supported metric, display alias and, for numeric records, a finite value with a supported rendering unit:

```text
usd
percent
rank
```

Source and snapshot records use their dedicated intents. Free-form string evidence is never compiled as an absolute observation.

Absolute candidates use `market_summary` as their canonical section and record `market_summary` plus `key_observations` as bounded section eligibility.

## Directional observations

Directional candidates are emitted only for evidence the current validator and renderer both support.

Supported numeric fields are:

```text
change_1h_pct
change_24h_pct
change_7d_pct
change_1d_pct
```

Supported status values are:

```text
up
down
rising
falling
positive
negative
unchanged
higher
lower
```

The compiler does not treat every field containing the word `change` as renderer-compatible. This is intentionally narrower than the validator’s defensive compatibility check.

Directional candidates use `key_observations` as their canonical section. Percentage movement materiality is classified deterministically:

```text
absolute movement >= 3%     high
absolute movement >= 1%     medium
smaller movement            low
```

These buckets are repository metadata only. They do not select or suppress a candidate.

## Numeric comparisons

The compiler groups numeric observations by the exact tuple:

```text
(field, unit)
```

Each pair must contain two distinct evidence IDs. A same-subject pair from the same source is omitted as a duplicate measurement rather than offered as a comparison.

The compiler never repairs or silently transforms evidence fields, units or comparison operands. In particular:

```text
price != price_usd
```

The candidate subject-key projection described above is metadata canonicalisation only; it is not measure or evidence normalisation.

Any future cross-source measure normalisation must be a separate, explicit and versioned evidence transformation that produces a new evidence-bundle identity before compilation.

### Relation derivation

The existing validator tolerance is retained:

```text
tolerance = max(abs(left), abs(right), 1.0) * 0.001
```

Relations are selected deterministically:

1. same-subject, different-source values inside tolerance become `approximately_equal` and `corroborated`;
2. divergent same-subject values from renderer-supported sources become `not_equal` and `divergent`;
3. opposite-sign directional measures become `opposite_direction`;
4. other values inside tolerance become `approximately_equal`;
5. remaining pairs become `greater_than` or `less_than`.

Operands are ordered by evidence ID before candidate construction. Slice 1 identity canonicalisation remains defence in depth.

Cross-subject comparisons use the repository subject marker:

```json
{"type": "market", "id": "cross-subject-comparison"}
```

The exact evidence IDs remain the authoritative operands.

## Source status

The compiler emits at most one `source_status` candidate per source subject.

A source subject must have exactly one status record. More than one status record is ambiguous and fails compilation rather than selecting one by traversal order.

The candidate may include up to three safe same-subject details after the status:

```text
reason
warning
```

Instruction-like untrusted strings are omitted. Coverage, selected-source metadata, timestamps, messages and unrelated source fields are not included in source-status candidates.

A healthy source status remains a status candidate. It does not become a data-quality limitation.

## Data-quality limitations

A limitation is emitted only when the evidence has explicit support and the deterministic renderer has a matching template.

Supported qualifying evidence is:

- a `status` or `quality_status` value in the bounded limitation vocabulary;
- a non-empty, safe `warning`;
- a non-empty `missing_symbols` set.

The limitation status vocabulary is:

```text
degraded
error
failed
incomplete
invalid
missing
skipped
stale
unavailable
warning
conflicting
valid-degraded
```

A qualifying status may include safe same-subject `reason` or `warning` detail.

The compiler deliberately does not emit limitations from:

- healthy `covered_symbols`;
- complete coverage;
- ordinary timestamps;
- selected-source metadata;
- `coverage`, `conflict`, `conflicts` or plural `warnings` records that have validator meaning but no current deterministic rendering template;
- unsafe instruction-like strings.

Unsupported quality records remain evidence. They are not silently rewritten into a supported limitation.

## Snapshot status

One `snapshot_status` candidate is emitted for each snapshot-subject `status` or `quality_status` record with evidence type `status`.

The candidate contains exactly one status record because the current renderer requires one status value per snapshot-status claim. Snapshot metadata never creates a market observation.

A degraded snapshot status may also independently support a data-quality limitation. The two candidates have different intents and remain separately selectable in later slices.

## Deterministic feature metadata

The compiler populates the Slice 1 bounded feature vocabulary without ranking:

- `materiality_bucket`;
- `cross_source`;
- `conflict_status`;
- `recency_bucket`;
- `quality_significance`;
- `section_eligibility`;
- `redundancy_group`;
- `corroboration_count`.

`recency_bucket` is currently `unknown`. The compiler does not depend on wall-clock execution time. A later reviewed rule may derive recency from canonical timestamps without changing candidate semantics.

Feature metadata is excluded from candidate identity. Intent, operands, relation, section, subject, metric, confidence and evidence-bundle identity remain semantic.

## Fail-closed errors

`ClaimCandidateCompilationError` records:

```text
code
path
message
```

Compilation fails for conditions such as:

- evidence-schema rejection;
- unsupported evidence-bundle version;
- invalid bundle-ID format;
- empty or non-object evidence records;
- duplicate evidence IDs;
- ambiguous multiple status records for one source subject;
- emitted candidate-schema rejection;
- stale or duplicate candidate IDs.

Invalid combinations are omitted when they are simply ineligible. Ambiguous or structurally invalid input fails the complete compilation.

## Determinism guarantees

For the same evidence-bundle identity and semantically equivalent evidence records:

- source dictionary order does not matter;
- evidence-array traversal order does not matter;
- candidate subject-key projection is deterministic and collision-resistant;
- candidate IDs are derived only from Slice 1 semantic identity fields;
- candidate IDs are unique;
- output candidate order is canonical;
- canonical JSON output is byte-stable.

The compiler does not recalculate the evidence-bundle ID from array presentation order. The evidence bundle is a previously governed canonical input, and its supplied identity remains the provenance boundary for all candidates.

## Validation proof

Focused tests compile the existing governed evidence fixture and prove:

- all six supported intents are produced when qualifying evidence exists;
- every candidate passes the candidate schema;
- every candidate ID matches its semantic payload;
- every candidate can be mapped in a focused test to a claim accepted by the unchanged semantic validator;
- every accepted claim renders byte-identically through the existing deterministic renderer;
- incompatible fields and units are absent;
- unsafe details and healthy coverage metadata do not become limitations;
- duplicate evidence and ambiguous source status fail closed;
- evidence permutations produce byte-identical candidate output.

These tests are compiler contract proofs, not the reviewed Slice 3 gold candidate corpus.

## Scope boundary

Slice 2 introduces no:

- reviewed gold corpus;
- ranking weights or selected candidate set;
- production candidate-to-plan reconstruction;
- model selection contract;
- provider request or paid evaluation;
- automatic report generation or publication;
- modification of historical Phase 5 prompts, plans, runners or evidence.

Slice 3 remains blocked until issue #287 and its implementation pull request are complete.
