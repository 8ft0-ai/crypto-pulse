<!-- Deterministically rendered by llm_analysis.render; do not edit generated text. -->

# Bitcoin declined less than Ethereum over the observed 24-hour period.

- Headline claim type: `comparison`
- Headline confidence: `high`
- Headline evidence: `market.asset.bitcoin.change_24h_pct`, `market.asset.ethereum.change_24h_pct`

> **Product boundaries**
> - AI-generated public demonstration content.
> - Not financial advice, investment research, a recommendation, or a trading signal.
> - Repository code owns validation, rendering, review, and publication.

## Market summary

- Bitcoin was recorded at US$62,739.
  - Claim type: `absolute_observation`
  - Confidence: `high`
  - Evidence: `market.asset.bitcoin.price_usd`

## Key observations

- Solana's observed 24-hour change was -4.11829%.
  - Claim type: `directional_observation`
  - Confidence: `high`
  - Evidence: `market.asset.solana.change_24h_pct`

## Risks and limitations

- Binance was skipped; the recorded reason was GitHub-hosted runners returned HTTP 451.
  - Claim type: `data_quality_limitation`
  - Confidence: `high`
  - Evidence: `source.binance.status`, `source.binance.reason`

## Data quality

- The selected snapshot passed with valid-ok quality.
  - Claim type: `absolute_observation`
  - Confidence: `high`
  - Evidence: `quality.snapshot.status`

## Source evidence note

- The bundle includes validated market-source status and an exchange cross-check status.
  - Claim type: `qualitative_interpretation`
  - Confidence: `high`
  - Evidence: `source.coingecko.status`, `source.defillama.status`, `source.coinbase_exchange.status`

---

Evidence bundle: `sha256:d86d7a2ee02a06f2c1d3225019f239a46478e85a7d6c4c531ed9371230689971`  
Analysis schema: `crypto-market-analysis/v1`  
Prompt version: `crypto-market-analysis/v1`
