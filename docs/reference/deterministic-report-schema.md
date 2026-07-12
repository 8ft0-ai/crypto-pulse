# Deterministic report schema

> **Mode:** Reference  
> **Audience:** CryptoPulse report developers, operators and reviewers  
> **Outcome:** Look up the source, path, front-matter, section-order and safety constraints for deterministic crypto reports.

## Canonical implementation

| Responsibility | Path |
| --- | --- |
| Generator | [`scripts/generate_crypto_report.py`](../../scripts/generate_crypto_report.py) |
| Validator | [`scripts/validate_crypto_report.py`](../../scripts/validate_crypto_report.py) |
| Source-snapshot validator | [`scripts/validate_crypto_snapshot.py`](../../scripts/validate_crypto_snapshot.py) |
| Source configuration | [`config/crypto_sources.yml`](../../config/crypto_sources.yml) |
| Generation workflow | [`.github/workflows/generate-deterministic-crypto-report.yml`](../../.github/workflows/generate-deterministic-crypto-report.yml) |

Schema version:

```text
deterministic-crypto-report/v1
```

## Source and output paths

One report is generated from exactly one validated snapshot:

```text
data/crypto/hourly/YYYY/MM/DD/HHMM_TZ_source_snapshot.json
```

With the normal `--output-root reports/crypto` setting, the output path is:

```text
reports/crypto/hourly/YYYY/MM/DD/HHMM_TZ.md
```

The generator inserts `hourly/` unless the supplied output root already ends in `hourly`.

## Generation command

```bash
python scripts/generate_crypto_report.py \
  --snapshot data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json \
  --output-root reports/crypto \
  --config config/crypto_sources.yml
```

The command prints the generated report path on success.

## Generation boundary

The generator:

- validates the selected snapshot before writing;
- accepts `valid-ok` and `valid-degraded` snapshots;
- rejects `invalid` snapshots without writing the normal report;
- uses only snapshot and reviewed configuration values;
- performs no network collection or hidden enrichment;
- performs no LLM call;
- does not build `_site/`, open a pull request, merge or deploy.

## Required front matter

| Field | Constraint |
| --- | --- |
| `schema_version` | `deterministic-crypto-report/v1` |
| `report_type` | `crypto_market_snapshot` |
| `source_snapshot` | Repository-relative source path used by the generator. |
| `generated_at_utc` | Snapshot generation time in UTC. |
| `generated_at_local` | Snapshot local generation time. |
| `timezone` | Snapshot timezone. |
| `timezone_abbreviation` | Local timezone abbreviation. |
| `cadence` | Snapshot cadence. |
| `quality_status` | `valid-ok` or `valid-degraded`. |
| `required_sources` | Required source names from computed quality. |
| `optional_exchange_sources` | Optional cross-check source names. |
| `selected_exchange_crosscheck` | Selected source or `null`. |
| `disabled_sources` | Disabled source names. |
| `no_investment_advice` | `true` |
| `llm_generated` | `false` |

## Required section order

```text
Title
Product boundary and non-investment-advice notice
Snapshot quality
Market summary
DeFi and stablecoin summary
Exchange cross-check summary
Evidence and source status
Scope limitations
```

## Snapshot quality section

The report records:

- computed quality status;
- each required source and status;
- each optional exchange source and status;
- blocking issues;
- non-blocking warnings.

A `valid-degraded` report must label the degraded state near the top and retain every warning. The generator does not smooth over unavailable optional evidence.

## Market and DeFi sections

The market table is generated from the snapshot asset records and includes available symbol, price, 1-hour, 24-hour and 7-day change, market capitalisation, volume, rank and update time values.

The DeFi section includes available total TVL and configured stablecoin values. Missing values are represented as not recorded rather than inferred.

## Exchange cross-check section

The report records:

- configured strategy;
- selected exchange source, if any;
- status and reason for configured optional and disabled sources;
- selected exchange rows where present.

Exchange-specific quote currencies remain visible and are not silently converted.

## Evidence and limitations

The report cites the exact source snapshot path and lists every snapshot source status. It ends with fixed limitations stating that it:

- uses one validated source snapshot;
- made no LLM call or hidden enrichment;
- is not financial advice, investment research, a recommendation, trading signal or buy/sell/hold call;
- may reflect stale, missing, degraded or erroneous source evidence recorded in the snapshot.

## Validation

Validate a generated report with:

```bash
python scripts/validate_crypto_report.py \
  reports/crypto/hourly/2026/07/08/1742_AEST.md \
  --root .
```

The generation workflow runs this validation before tests, site generation, rendered-path proof, branch creation and pull-request creation.

For the source quality states, see [Source snapshot quality](source-snapshot-quality.md). For the generated pull-request proof fields, see [Generated report PR evidence](generated-report-pr-evidence.md).
