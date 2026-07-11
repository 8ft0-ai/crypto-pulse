# GPT-4o mini public-data demo decision

## Decision

**Outcome:** `public-demo-no-go` under the current free-text automatic-acceptance contract.

**Selected model:** none.

This is not a finding that GPT-4o mini cannot perform the CryptoPulse analysis task. The protected evidence shows the opposite: the model consumed the complete governed corpus and repeatedly produced coherent strict structured analyses. The no-go applies to the current requirement that model-authored prose pass every lexical and semantic validator without review or deterministic rendering.

## Capability result

The core project proposition is demonstrated:

> An LLM can consume a curated CryptoPulse evidence bundle and construct an evidence-referenced market analysis response.

Protected run `29151358149` completed all bounded calls from trusted main commit `96f1c680c700318b0ed1d26203d2cd0555f5f5ac`.

```text
Requested model:              openai/gpt-4o-mini
Actual provider:              OpenAI
Route preflight:              passed
Logical calls / HTTP attempts: 12 / 12
Corpus generations:           10 / 10
Cross-model fallback:         0
Provider fallback:            0
Total cost:                   USD 0.0185832
Approved ceiling:             USD 0.15
Automatic publication:        disabled
```

Across the corpus, there were no failures in:

- provider or model identity;
- JSON or provider structured output;
- canonical schema validation;
- evidence-ID referential integrity;
- policy boundaries;
- prompt-injection compliance;
- cross-model fallback controls;
- experiment cost controls.

The prompt-injection cases remained inside the trusted instructions. The adversarial disagreement cases did not produce an invalid `source_disagreement` claim.

## Qualification result

The exact qualification rule required ten hard passes. The diagnostic corpus produced:

```text
Hard passes: 1 / 10
Rejected:    9 / 10
```

The diagnostic distribution was highly concentrated:

| Diagnostic | Count | Interpretation |
|---|---:|---|
| `value/untraceable_number` | 16 | Exact negative values were retained in `quoted_values`, but prose used rounded positive magnitudes without the required approximation wording. |
| `semantic/invalid_data_quality_support` | 3 | Grounded timestamp or selected-source facts were classified as `data_quality_limitation` rather than a permitted claim form. |
| `value/entity_mismatch` | 1 | The cited string value `coinbase_exchange` was rendered as `Coinbase Exchange`. |

Sixteen of twenty findings were therefore the same lexical pattern. The model did not invent the underlying values: each exact negative source value and evidence ID remained present in the structured claim.

The remaining four findings were claim-taxonomy or label-rendering mismatches. They were not unsupported prices, fabricated sources, advice, forecasts, trading signals, or actions.

## Reproducibility

The two completions for every case had different raw-completion hashes. Exact byte-level reproducibility is therefore unsuitable as a primary expectation for model-authored prose.

The responses were nevertheless structurally stable: they consistently used the same model and provider, retained source values and evidence references, stayed within the same policy boundary, and produced similar evidence-backed market summaries. This supports evaluating reproducibility at the structured claim-plan level rather than at the final prose byte level.

## Architectural conclusion

The current pipeline gives the LLM two responsibilities:

1. decide what supported analytical claims to make; and
2. generate exact governed wording for signs, rounding, units, dates, aliases and claim taxonomy.

The diagnostic run shows that responsibility two is causing most hard failures. Continuing to add wording-specific validator exceptions would overfit the system to recent stochastic completions.

The follow-up is planning issue #226:

> Separate governed claim selection from deterministic prose rendering.

The LLM should remain responsible for selecting, organising and relating evidence-backed claims. Repository-owned code should deterministically render numeric signs, rounding, units, dates and approved labels. Raw model output and provenance should remain available for review, but model-authored prose should not be the source of truth for automatic publication.

## Final boundary

This decision applies only to the explicit public/evaluation-only demonstration profile:

```text
Input classification:                    public-market-data | evaluation-only
ZDR:                                     false
Provider training/data collection:       deny
Ordinary provider retention accepted:    true
Automatic generation:                    false
Publication:                             false
```

It does not approve sensitive data, scheduled generation, production use or automatic publication.

## Evidence

- Protected run: `29151358149`
- Trusted main SHA: `96f1c680c700318b0ed1d26203d2cd0555f5f5ac`
- Artifact ID: `8248289872`
- Artifact digest: `sha256:9e8d6187c3ec701040cd2f2021002a5966cf0aec333f1b2a15f4d56bffa7c282`
- Architectural follow-up: #226
