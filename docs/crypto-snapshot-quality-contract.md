# Crypto snapshot quality contract

Issue: #65  
Parent: #63

Crypto source snapshots are evidence artefacts. A snapshot can be well-formed JSON while still being unsuitable for downstream report generation, so ingestion and validation use an explicit quality classification.

## Quality states

| State | Meaning | Workflow behaviour |
| --- | --- | --- |
| `valid-ok` | Required CoinGecko market evidence and required DefiLlama DeFi/stablecoin evidence are present with `ok` source status. Optional exchange cross-checks are either not enabled or have no blocking problems. | The snapshot validator exits successfully and the generated evidence PR may be opened. |
| `valid-degraded` | Required sources are present and usable, but one or more optional exchange cross-checks failed, warned, were skipped, or were missing. | The snapshot validator exits successfully and the generated evidence PR may be opened with warnings. |
| `invalid` | A required source is missing or has a non-`ok` status. Later validator hardening also treats required-source freshness, malformed data, and implausible required fields as invalid. | The snapshot validator exits non-zero. In the scheduled workflow this stops before branch creation. |

## Source criticality

Required sources block publication when they are missing or unhealthy:

```yaml
sources:
  coingecko:
    required: true
    role: market
  defillama:
    required: true
    role: defi_stablecoins
```

Optional exchange cross-checks do not block evidence publication when the required sources remain healthy. They are used to record independent price evidence and to classify otherwise valid snapshots as degraded when the optional cross-check path is incomplete.

```yaml
exchange_crosschecks:
  required: false
  strategy: first_successful
```

The MVP cross-check priority is:

1. Coinbase Exchange public ticker, USD pairs.
2. Kraken public ticker, USD pairs.
3. OKX public spot ticker, USDT pairs.

Disabled or non-MVP sources remain documented in config so generated PRs can explain why they are not part of the runner path. Binance is explicitly disabled for GitHub-hosted runners after returning HTTP 451 during discovery and ingestion.

## Snapshot metadata

New snapshots may include a top-level `quality` object:

```json
{
  "quality": {
    "status": "valid-ok",
    "required_sources": ["coingecko", "defillama"],
    "optional_exchange_sources": ["coinbase_exchange", "kraken", "okx"],
    "disabled_sources": ["binance", "bybit", "cryptocompare"],
    "blocking_issues": [],
    "non_blocking_warnings": []
  }
}
```

The validator recomputes the quality status from the snapshot and source config. If an embedded `quality.status` disagrees with the computed status, validation fails.

## Boundary

This contract does not generate reports, call an LLM, introduce secrets, or auto-merge generated PRs. It only distinguishes usable, degraded, and invalid source evidence so later report generation can consume snapshots safely.
