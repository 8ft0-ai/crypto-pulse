<!-- Deterministically rendered by llm_analysis.claim_plan_render; do not edit generated text. -->

# Governed CryptoPulse market analysis

> **Product boundaries**
> - AI-generated public demonstration content.
> - Not financial advice, investment research, a recommendation, or a trading signal.
> - Repository code owns validation, rendering, review, and publication.

## Market summary

- Bitcoin price was US$62,031.
  - Claim ID: `claim-cfd7709eedb67dd80a2dcded3ddfeeaa6889df620de410329f662681a9423728`
  - Intent: `absolute_observation`
  - Confidence: `high`
  - Evidence: `market.asset.bitcoin.price_usd`

## Key observations

- Solana decreased by approximately 4.82% over 24 hours.
  - Claim ID: `claim-569d50b55ed2fce91d5fb0b8c06f82ea6354420bce32230cf35a9a3cb2b928e0`
  - Intent: `directional_observation`
  - Confidence: `high`
  - Evidence: `market.asset.solana.change_24h_pct`
- Bitcoin 1-hour change (approximately -0.06%) moved in the opposite direction to Ethereum 1-hour change (approximately 0.03%).
  - Claim ID: `claim-7fba1f4e9aeb6531bda575f2f9aa6e517bafe5142fdb3f0bff3bb79ebc6c9238`
  - Intent: `comparison`
  - Confidence: `high`
  - Evidence: `market.asset.bitcoin.change_1h_pct`, `market.asset.ethereum.change_1h_pct`
- Bitcoin price (US$62,031) was greater than Ethereum price (US$1,737.9).
  - Claim ID: `claim-9573f39667e82c618f9980bcd6eca82f47dd71c34777646ef1ae0ef35e31d6da`
  - Intent: `comparison`
  - Confidence: `high`
  - Evidence: `market.asset.bitcoin.price_usd`, `market.asset.ethereum.price_usd`

## Data quality

- Data quality was limited because Binance source status was skipped. Recorded reason: GitHub-hosted runners returned HTTP 451.
  - Claim ID: `claim-79315d64dbe4abd9700f01bfd84e1188ffcbe391bd2f107a76c808a1454881fb`
  - Intent: `data_quality_limitation`
  - Confidence: `high`
  - Evidence: `source.binance.reason`, `source.binance.status`

---

Evidence bundle: `sha256:cac65904dcff4656ee84ca9be906390a5219ad6b7dff3d2d546ccc69028feda3`  
Claim-plan schema: `crypto-market-claim-plan/v1`  
Prompt version: `crypto-market-claim-plan/v1`  
Renderer version: `crypto-market-claim-plan-renderer/v1`
