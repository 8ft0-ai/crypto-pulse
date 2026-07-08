# Crypto source cross-check discovery

Issue: #64  
Parent: #63

## Summary

This discovery tested public exchange / market-data sources as potential cross-check inputs for CryptoPulse source snapshots.

The test was run from GitHub Actions so the results reflect the same broad runner context used by scheduled ingestion. This matters because Binance is reachable from some environments but returned HTTP 451 from GitHub-hosted runners during ingestion.

Discovery run:

```text
Validate CryptoPulse PR run: 28917746765
Artifact: crypto-crosscheck-discovery-results
Generated at: 2026-07-08T04:34:09Z
```

## Results

| Source | Result from GitHub Actions | Notes |
| --- | --- | --- |
| Coinbase Exchange public ticker | `ok` | BTC-USD, ETH-USD, and SOL-USD returned JSON with price, volume, bid/ask, and timestamp fields. |
| Kraken public ticker | `ok` | One batched request for XBTUSD, ETHUSD, and SOLUSD returned JSON with an empty error list and three result objects. |
| OKX public spot ticker | `ok` | BTC-USDT, ETH-USDT, and SOL-USDT returned JSON with `code: 0` and one ticker row each. |
| Bybit public spot ticker | `failed` | BTCUSDT, ETHUSDT, and SOLUSDT all returned HTTP 403 Forbidden. |
| CryptoCompare price multi full | `failed` | BTC/ETH/SOL to USD returned HTTP 401 Unauthorized without an API key. |
| Binance public 24h ticker | `failed` | BTCUSDT, ETHUSDT, and SOLUSDT all returned HTTP 451 from GitHub Actions. |

## Probe details

### Coinbase Exchange public ticker

Coinbase succeeded for all three target assets.

```text
BTC-USD: HTTP 200, price/volume/time returned
ETH-USD: HTTP 200, price/volume/time returned
SOL-USD: HTTP 200, price/volume/time returned
```

Observed sample fields included:

```text
price
volume
bid
ask
time
trade_id
```

This is the cleanest replacement candidate for the current Binance cross-check because it supports USD pairs directly and returns a small ticker payload per asset.

### Kraken public ticker

Kraken succeeded for the batched ticker request:

```text
XBTUSD,ETHUSD,SOLUSD: HTTP 200
error: []
result: 3 objects
```

This is a strong secondary option. The main implementation consideration is that Kraken uses exchange-specific pair names and dynamic result keys, so the normaliser needs a small mapping layer.

### OKX public spot ticker

OKX succeeded for all three target pairs:

```text
BTC-USDT: HTTP 200, code 0, data[1]
ETH-USDT: HTTP 200, code 0, data[1]
SOL-USDT: HTTP 200, code 0, data[1]
```

OKX is a good fallback option, but it is USDT-quoted rather than USD-quoted for this MVP test. That is still useful for cross-checking, but should be labelled as a USDT market rather than direct USD evidence.

### Bybit public spot ticker

Bybit failed from GitHub Actions:

```text
BTCUSDT: HTTP 403 Forbidden
ETHUSDT: HTTP 403 Forbidden
SOLUSDT: HTTP 403 Forbidden
```

Do not use Bybit as an MVP runner-based source unless a later discovery shows a reliable access pattern.

### CryptoCompare price multi full

CryptoCompare failed without an API key:

```text
BTC/ETH/SOL-USD: HTTP 401 Unauthorized
```

Do not use CryptoCompare in the no-secrets MVP path. It may be reconsidered later if the project introduces managed secrets and an explicit API-key policy.

### Binance public 24h ticker

Binance again failed from GitHub Actions:

```text
BTCUSDT: HTTP 451
ETHUSDT: HTTP 451
SOLUSDT: HTTP 451
```

This confirms Binance should not be treated as a required source when ingestion runs from GitHub-hosted runners.

## Recommendation

Use this MVP source strategy:

```text
Primary market source:
- CoinGecko remains the primary market-data source.

Exchange cross-check priority:
1. Coinbase Exchange public ticker, USD pairs
2. Kraken public ticker, USD pairs
3. OKX public spot ticker, USDT pairs

Optional / disabled for GitHub-hosted runner context:
- Binance: optional only, currently HTTP 451
- Bybit: do not use for MVP, currently HTTP 403
- CryptoCompare: do not use for no-secrets MVP, currently HTTP 401
```

## Proposed config direction

A future config could make source priority and criticality explicit:

```yaml
exchange_crosschecks:
  required: false
  strategy: first_successful
  sources:
    - name: coinbase_exchange
      enabled: true
      quote: USD
      pairs:
        BTC: BTC-USD
        ETH: ETH-USD
        SOL: SOL-USD
    - name: kraken
      enabled: true
      quote: USD
      pairs:
        BTC: XBTUSD
        ETH: ETHUSD
        SOL: SOLUSD
    - name: okx
      enabled: true
      quote: USDT
      pairs:
        BTC: BTC-USDT
        ETH: ETH-USDT
        SOL: SOL-USDT
    - name: binance
      enabled: false
      quote: USDT
      reason: GitHub-hosted runners returned HTTP 451
```

## Follow-up implementation

The next implementation issue should not simply replace Binance with a single hard-coded source. The more resilient approach is:

```text
try Coinbase Exchange first;
if unavailable, try Kraken;
if unavailable, try OKX;
record every attempted source status;
classify the snapshot as valid-ok, valid-degraded, or invalid using #65 and #66.
```

## Out of scope for this discovery

- No ingestion source changes were made.
- No report generation was introduced.
- No LLM calls were introduced.
- No secrets or paid API keys were introduced.
- No auto-merge behaviour was changed.
