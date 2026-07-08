# Deterministic crypto report Markdown schema

This document defines the first deterministic Markdown report shape for CryptoPulse source snapshots. It is a design contract only: it does not introduce report generation, live publishing, LLM calls, or any change to the generated `_site/` output.

CryptoPulse reports are demonstration content only. They must not be treated as financial advice, investment research, recommendations, trading signals, target prices, or personalised advice.

## Source and output convention

A deterministic report is generated from exactly one validated source snapshot JSON file.

Expected source snapshot path:

```text
data/crypto/hourly/YYYY/MM/DD/HHMM_TZ_source_snapshot.json
```

Expected raw Markdown report path:

```text
reports/crypto/YYYY/MM/DD/HHMM_TZ.md
```

For example:

```text
data/crypto/hourly/2026/07/08/1434_AEST_source_snapshot.json
reports/crypto/2026/07/08/1434_AEST.md
```

The raw Markdown report is the source of truth for the site. Generated `_site/` output remains disposable and must not be committed.

## Generation boundary

The report generator must:

- load one snapshot JSON file;
- validate it before generating Markdown;
- fail without writing a report for `invalid` snapshots;
- generate a report for `valid-ok` and `valid-degraded` snapshots;
- use only fields present in the validated snapshot and deterministic formatting rules;
- avoid LLM calls, secrets, paid APIs, hidden enrichment, target prices, buy/sell calls, portfolio instructions, or personalised recommendations.

## Required front matter

Each generated report must start with YAML front matter. Required fields are:

```yaml
---
schema_version: deterministic-crypto-report/v1
report_type: crypto_market_snapshot
source_snapshot: data/crypto/hourly/YYYY/MM/DD/HHMM_TZ_source_snapshot.json
generated_at_utc: "2026-07-08T04:34:52Z"
generated_at_local: "2026-07-08T14:34:52+10:00"
timezone: Australia/Sydney
timezone_abbreviation: AEST
cadence: hourly
quality_status: valid-ok
required_sources:
  - coingecko
  - defillama
optional_exchange_sources:
  - coinbase_exchange
  - kraken
  - okx
selected_exchange_crosscheck: coinbase_exchange
disabled_sources:
  - binance
  - bybit
  - cryptocompare
no_investment_advice: true
llm_generated: false
---
```

Optional front matter may include source-status summaries, configured asset symbols, or generator version, provided those values are deterministic and derived from the validated snapshot or repository config.

## Required sections

The Markdown body must include these sections in this order.

### 1. Title

The title should be deterministic and timestamp-based, for example:

```markdown
# Crypto market evidence snapshot — 8 July 2026, 14:34 AEST
```

### 2. Product boundary and non-investment-advice notice

The report must clearly state that it is demonstration content generated from source evidence. It must state that it is not financial advice, investment research, a recommendation, a trading signal, or a call to buy, sell, or hold any asset.

### 3. Snapshot quality

The report must show:

- `quality.status`;
- required sources and their statuses;
- optional exchange sources and their statuses;
- selected exchange cross-check, if any;
- disabled/non-MVP sources and reasons;
- blocking issues;
- non-blocking warnings.

For `valid-ok`, blocking issues and non-blocking warnings should be shown as none.

For `valid-degraded`, the section must visibly label the report as degraded and list every non-blocking warning. The report may still be generated, but the warning context must be near the top of the report.

### 4. Market summary

The report must include one deterministic row per configured required asset, currently BTC, ETH, and SOL. At minimum each row should include:

- symbol;
- name;
- USD price;
- market capitalisation;
- 24-hour volume;
- 1-hour, 24-hour, and 7-day percentage changes;
- market-cap rank;
- source update timestamp.

The section must describe only what the numbers show. It must not infer trading direction, entry points, exit points, targets, or recommendations.

### 5. DeFi and stablecoin summary

The report must include:

- total DeFi TVL in USD where present;
- the major stablecoins required by config, currently USDT and USDC;
- each stablecoin price and circulating USD value;
- any peg-deviation warnings emitted by the validator.

### 6. Exchange cross-check summary

The report must include:

- configured strategy, initially `first_successful`;
- selected exchange source, if any;
- per-source status for Coinbase Exchange, Kraken, and OKX;
- rows for the selected exchange cross-check when available;
- skipped-source reasons for later enabled sources when the first successful source satisfied the strategy;
- disabled-source reasons for Binance, Bybit, and CryptoCompare.

If all optional exchange cross-checks fail but required sources remain healthy, the report is `valid-degraded`, not `invalid`.

### 7. Evidence and source status

The report must reference the exact source snapshot path and list every source status included in the snapshot. It must include enough evidence for a reader to trace the report back to the raw JSON.

### 8. Scope limitations

The report must end with deterministic limitations, including:

- generated from one validated snapshot;
- no LLM calls;
- no hidden enrichment;
- no investment advice;
- no trading recommendation;
- may contain stale, missing, degraded, or erroneous source data if the snapshot says so.

## Handling degraded and invalid snapshots

`valid-ok` snapshots can produce standard deterministic reports.

`valid-degraded` snapshots can produce deterministic reports only when the degraded state is explicit in front matter and body. The report must show non-blocking warnings near the top and avoid smoothing over missing optional evidence.

`invalid` snapshots must not produce a report by default. The generator should fail before writing any Markdown. If a future operator needs an invalid diagnostic artefact, that must be a separate issue and must not use the normal report path.

## Illustrative Markdown skeleton

```markdown
---
schema_version: deterministic-crypto-report/v1
report_type: crypto_market_snapshot
source_snapshot: data/crypto/hourly/2026/07/08/1434_AEST_source_snapshot.json
generated_at_utc: "2026-07-08T04:34:52Z"
generated_at_local: "2026-07-08T14:34:52+10:00"
timezone: Australia/Sydney
timezone_abbreviation: AEST
cadence: hourly
quality_status: valid-ok
required_sources:
  - coingecko
  - defillama
optional_exchange_sources:
  - coinbase_exchange
  - kraken
  - okx
selected_exchange_crosscheck: coinbase_exchange
disabled_sources:
  - binance
  - bybit
  - cryptocompare
no_investment_advice: true
llm_generated: false
---

# Crypto market evidence snapshot — 8 July 2026, 14:34 AEST

## Product boundary and non-investment-advice notice

This report is deterministic demonstration content generated from one validated source snapshot. It is not financial advice, investment research, a recommendation, a trading signal, or a call to buy, sell, or hold any asset.

## Snapshot quality

Status: `valid-ok`

Blocking issues: none.

Non-blocking warnings: none.

## Market summary

| Asset | Price USD | 1h | 24h | 7d | Market cap USD | 24h volume USD | Updated |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| BTC | 60,000.00 | 0.10% | 1.20% | 2.30% | 1,200,000,000,000 | 10,000,000,000 | 2026-07-08T04:34:00Z |
| ETH | 3,000.00 | 0.20% | 1.30% | 2.40% | 360,000,000,000 | 5,000,000,000 | 2026-07-08T04:34:00Z |
| SOL | 100.00 | 0.30% | 1.40% | 2.50% | 55,000,000,000 | 1,000,000,000 | 2026-07-08T04:34:00Z |

## DeFi and stablecoin summary

Total DeFi TVL: USD 100,000,000,000.

| Stablecoin | Price USD | Circulating USD |
| --- | ---: | ---: |
| USDT | 1.00 | 100,000,000,000 |
| USDC | 1.00 | 50,000,000,000 |

## Exchange cross-check summary

Strategy: `first_successful`

Selected exchange cross-check: `coinbase_exchange`

| Source | Status | Notes |
| --- | --- | --- |
| coinbase_exchange | ok | selected |
| kraken | skipped | not attempted after Coinbase Exchange satisfied first_successful strategy |
| okx | skipped | not attempted after Coinbase Exchange satisfied first_successful strategy |

## Evidence and source status

Source snapshot: `data/crypto/hourly/2026/07/08/1434_AEST_source_snapshot.json`

## Scope limitations

This report uses only the validated snapshot listed above. It made no LLM calls, used no hidden enrichment, and contains no investment advice, target price, or trading recommendation.
```
