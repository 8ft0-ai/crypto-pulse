<!-- Deterministically rendered by llm_analysis.claim_plan_render; do not edit generated text. -->

# Governed CryptoPulse market analysis

> **Product boundaries**
> - AI-generated public demonstration content.
> - Not financial advice, investment research, a recommendation, or a trading signal.
> - Repository code owns validation, rendering, review, and publication.

## Market summary

- Bitcoin price was US$62,739.
  - Claim ID: `claim-btc-price`
  - Intent: `absolute_observation`
  - Confidence: `high`
  - Evidence: `market.asset.bitcoin.price_usd`
- Bitcoin decreased by approximately 0.55% over 24 hours.
  - Claim ID: `claim-btc-direction`
  - Intent: `directional_observation`
  - Confidence: `high`
  - Evidence: `market.asset.bitcoin.change_24h_pct`

## Key observations

- Bitcoin price (US$62,739) was greater than Ethereum price (US$1,751.92).
  - Claim ID: `claim-btc-eth-price-comparison`
  - Intent: `comparison`
  - Confidence: `high`
  - Evidence: `market.asset.bitcoin.price_usd`, `market.asset.ethereum.price_usd`

## Source status

- CoinGecko source status was ok.
  - Claim ID: `claim-coingecko-status`
  - Intent: `source_status`
  - Confidence: `high`
  - Evidence: `source.coingecko.status`

## Data quality

- Data quality was limited because Binance source status was skipped. Recorded reason: GitHub-hosted runners returned HTTP 451.
  - Claim ID: `claim-binance-limitation`
  - Intent: `data_quality_limitation`
  - Confidence: `high`
  - Evidence: `source.binance.status`, `source.binance.reason`

## Risks and limitations

- The source snapshot status was valid-ok.
  - Claim ID: `claim-snapshot-status`
  - Intent: `snapshot_status`
  - Confidence: `high`
  - Evidence: `quality.snapshot.status`

---

Evidence bundle: `sha256:d86d7a2ee02a06f2c1d3225019f239a46478e85a7d6c4c531ed9371230689971`  
Claim-plan schema: `crypto-market-claim-plan/v1`  
Prompt version: `crypto-market-claim-plan/v1`  
Renderer version: `crypto-market-claim-plan-renderer/v1`
