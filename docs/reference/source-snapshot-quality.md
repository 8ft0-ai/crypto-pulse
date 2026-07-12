# Source snapshot quality

> **Mode:** Reference  
> **Audience:** CryptoPulse operators, report developers and reviewers  
> **Outcome:** Look up the quality states, source criticality and validator behaviour applied to crypto source snapshots.

## Canonical implementation and configuration

| Responsibility | Path |
| --- | --- |
| Source configuration | [`config/crypto_sources.yml`](../../config/crypto_sources.yml) |
| Snapshot validator | [`scripts/validate_crypto_snapshot.py`](../../scripts/validate_crypto_snapshot.py) |
| Checked-in source evidence | `data/crypto/hourly/**/*_source_snapshot.json` |

## Quality states

| State | Meaning | Validator behaviour |
| --- | --- | --- |
| `valid-ok` | Required structure, configured required sources and quality checks pass without non-blocking warnings. | Exit status `0`; downstream deterministic processing is permitted. |
| `valid-degraded` | Required evidence remains usable, but optional source, freshness, warning or coverage limitations remain. | Exit status `0`; warnings are written to standard error and must remain visible downstream. |
| `invalid` | A blocking structure, required-source, freshness, consistency or plausibility rule failed. | Exit status `1`; normal report and governed-analysis workflows must stop. |

## Source criticality

The current source configuration defines required market and DeFi/stablecoin sources. Missing or unhealthy required sources are blocking.

Optional exchange cross-checks provide independent price evidence but do not make an otherwise healthy snapshot invalid merely because a later optional source was skipped or unavailable. The current strategy is configured under:

```yaml
exchange_crosschecks:
  required: false
  strategy: first_successful
```

The configuration, not this page, is authoritative for the active source list, priority, pairs, freshness limits and disabled-source reasons.

## Embedded quality object

A snapshot may contain:

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

The validator recomputes quality from the complete snapshot and current configuration. If an embedded `quality.status` disagrees with the computed result, validation fails.

## Structural validation

The validator requires:

- a JSON object at the document root;
- required top-level and `run` keys;
- valid generation timestamps;
- at least one source-status record;
- valid market, exchange and DeFi shapes;
- list-valued warnings and errors;
- source and quality values compatible with the current configuration.

## Blocking and non-blocking findings

Blocking findings populate `blocking_issues` and produce `invalid`. They include required-source failures and other configured hard rules.

Non-blocking findings populate `non_blocking_warnings` and produce `valid-degraded` when no blocking issue exists. A degraded result is accepted by the validator but must not be presented as complete or silently normalised to `valid-ok`.

## Command interface

Validate one file:

```bash
python scripts/validate_crypto_snapshot.py \
  data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json
```

Validate every matching snapshot beneath a directory:

```bash
python scripts/validate_crypto_snapshot.py data/crypto/hourly/2026/07/08
```

Use an explicit configuration:

```bash
python scripts/validate_crypto_snapshot.py <path> --config config/crypto_sources.yml
```

The command selects files ending in `_source_snapshot.json` recursively when given a directory.

## Boundary

Quality classification does not generate a report, call an LLM, publish a site, create a pull request or merge any change. It determines whether downstream processing may proceed and what limitations must remain visible.

For the operating procedure, see [Validate a source snapshot](../how-to/validate-a-source-snapshot.md). Historical evidence behind the exchange source priority is preserved in [`evaluation/source-crosscheck-discovery.md`](../../evaluation/source-crosscheck-discovery.md).
