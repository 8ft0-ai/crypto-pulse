# Phase 6 deterministic ranking baseline

> **Classification:** repository-owned evaluation evidence; no model or provider output.

- Ranking configuration: `config/claim-candidate-ranking-v1.yml`
- Ranking configuration SHA-256: `87370654f596019fd75b83ea96fe78aa184a0e5c97f664ebdcfe413672cca9a9`
- Gold corpus: `evaluation/phase-06/claim-candidate-gold/manifest.yml`
- Overall status: `pass`
- Cases rendered without an LLM: `5 / 5`
- Selected useful precision: `26 / 35 (74.29%)`
- Selected useful recall: `26 / 38 (68.42%)`

## Case summary

| Case | Class | Candidates | Selected | Useful | Precision | Recall | Sections |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `historical-degraded-sparse` | `historical` | 201 | 7 | 5 | 71.43% | 62.50% | market_summary, key_observations, data_quality |
| `historical-normal-crosschecked` | `historical` | 230 | 7 | 6 | 85.71% | 60.00% | market_summary, key_observations, data_quality |
| `historical-material-move` | `historical` | 230 | 7 | 6 | 85.71% | 75.00% | market_summary, key_observations, data_quality |
| `adversarial-prompt-injection` | `evaluation-only` | 230 | 7 | 5 | 71.43% | 83.33% | market_summary, key_observations, data_quality |
| `adversarial-source-disagreement` | `evaluation-only` | 230 | 7 | 4 | 57.14% | 66.67% | market_summary, key_observations, data_quality |

## `historical-degraded-sparse`

- Classification: `historical`
- Bundle: `sha256:d544ecc0ed65fea25a6a0389fabf68b4fd6b854a95c3541ed596554333b13a58`
- Candidate set: `201` candidates, SHA-256 `330769db9e7f13663bdd34ccaa49bbfa73cc7cda832196072e252df82ef9eaf6`
- Selected set: `7` candidates, SHA-256 `9e9f5d51a552f3f4b91feee24094eced5b4a7eac9adbd84811b66838d436eae2`
- Claim plan SHA-256: `5eea2bd99b704d857a0a908b1faeceec12e360652db2c085ea0a064c268e59f9`
- Rendered Markdown SHA-256: `a7fc6984cad632853a4ee20177b92abeaa17ed5c8b3581341168d6f9a404f2b4`
- Useful precision: `5 / 7 (71.43%)`
- Useful recall: `5 / 8 (62.50%)`
- Candidate permutation stable: `true`
- Evidence permutation stable: `true`

### Selected claims

| Candidate | Stage | Score vector | Gold expectation | Rendered claim |
| --- | --- | --- | --- | --- |
| `claim-candidate:sha256:2313cb3dad570e0ed7a515ea801f7b1fbc02df9fd0ec31ed8e6962c560e692bd` | `required_slot:primary-market-price` | `[0, 0, 0, 0, 10, 10, 1, 2, 0, 1, 1]` | `btc-price` | Bitcoin price was US$62,804. |
| `claim-candidate:sha256:e0dd468973e539311540ee0fdbd52f87910286f0c6c28b4494638150a1df81f1` | `required_slot:daily-market-movement` | `[0, 0, 2, 0, 9, 10, 1, 3, 0, 1, 1]` | `sol-24h-direction` | Solana decreased by approximately 2.55% over 24 hours. |
| `claim-candidate:sha256:8c8dd2eed50ca18cbb65d8a0af15a3ef9fe45a74f9e90f953fefb67eaa2fa3a2` | `required_slot:primary-market-price-comparison` | `[0, 0, 0, 2, 10, 10, 1, 5, 0, 1, 1]` | `btc-eth-price-comparison` | Bitcoin price (US$62,804) was greater than Ethereum price (US$1,754.13). |
| `claim-candidate:sha256:cded157763793ac9cadce060fb82346046e182865999566fddce43b52ddd8b72` | `required_slot:primary-market-movement-comparison` | `[0, 0, 0, 2, 9, 10, 0, 5, 0, 1, 1]` | `—` | Bitcoin 24-hour change (approximately -0.65%) was greater than Ethereum 24-hour change (approximately -0.93%). |
| `claim-candidate:sha256:c7f5389de3d165ab72bbb94a38e377d3021d4897c4fa96bd0bee075bc30668db` | `required_slot:explicit-data-quality-limitation` | `[0, 2, 0, 0, 4, 8, 1, 4, 0, 1, 1]` | `snapshot-degradation` | Data quality was limited because the source snapshot status was valid-degraded. |
| `claim-candidate:sha256:abb461f78e176fad623e083df4978b3f6cccf78645f2b35fa23419605ee516f9` | `required_slot:snapshot-status` | `[0, 2, 0, 0, 4, 8, 0, 1, 0, 1, 1]` | `snapshot-status` | The source snapshot status was valid-degraded. |
| `claim-candidate:sha256:3e26783b7d32a7ef249c79f56a89cf37a44c111d9a21e8b15110d4754dc978ca` | `ranked_fill` | `[0, 0, 3, 0, 8, 10, 1, 3, 0, 1, 1]` | `—` | Ethereum increased by approximately 10.17% over 7 days. |

### Canonical plan

- Analysis order: `['market_summary', 'key_observations', 'data_quality']`
- Section counts: `{'market_summary': 1, 'key_observations': 4, 'data_quality': 2}`
- Intent counts: `{'absolute_observation': 1, 'directional_observation': 2, 'comparison': 2, 'data_quality_limitation': 1, 'snapshot_status': 1}`
- Unique redundancy groups: `7`
- Distinct candidate subjects: `5`

## `historical-normal-crosschecked`

- Classification: `historical`
- Bundle: `sha256:e1e26a91350b8c58effa35a1bc3ca2e587d3ea7f5f6c13f7228d6e11c516d276`
- Candidate set: `230` candidates, SHA-256 `0e3fba876a8fc81f61dd567e7536cc281d59addc55961bd81b3a928d406c8f4c`
- Selected set: `7` candidates, SHA-256 `43ba6d185d23add3f30d8f3d9fcd793b7fa3b49a4e562f3e0b337d49c104cb75`
- Claim plan SHA-256: `2af0023e4e853d6b98442b6e7c9b4ef330f73ec88c05a516e7fd46b32e2ee7fc`
- Rendered Markdown SHA-256: `27e8f1b9b11a3042597b1e5e2bed46d19709ba704166cd34ef7909dbbc2250a2`
- Useful precision: `6 / 7 (85.71%)`
- Useful recall: `6 / 10 (60.00%)`
- Candidate permutation stable: `true`
- Evidence permutation stable: `true`

### Selected claims

| Candidate | Stage | Score vector | Gold expectation | Rendered claim |
| --- | --- | --- | --- | --- |
| `claim-candidate:sha256:5739d7ea46b521a4903c9a0d5371015128977beec6a4230e86a82807d5a2d1c8` | `required_slot:primary-market-price` | `[0, 0, 0, 0, 10, 10, 1, 2, 0, 1, 1]` | `btc-price` | Bitcoin price was US$62,739. |
| `claim-candidate:sha256:ba2389ae233e2da23c6d35f64ab3ccdb056d9729b72101d64826308cf6a11d17` | `required_slot:daily-market-movement` | `[0, 0, 3, 0, 9, 10, 1, 3, 0, 1, 1]` | `sol-24h-direction` | Solana decreased by approximately 4.12% over 24 hours. |
| `claim-candidate:sha256:d1a902a6a321d333593e226fa29a95c9157428bae2132c5752163def4002d911` | `required_slot:primary-market-price-comparison` | `[0, 0, 0, 2, 10, 10, 1, 5, 0, 1, 1]` | `btc-eth-price-comparison` | Bitcoin price (US$62,739) was greater than Ethereum price (US$1,751.92). |
| `claim-candidate:sha256:62316836cdf1b100c9a2236c0138d7106e7e7ba8fc7c864af0036ebc57deb989` | `required_slot:primary-market-movement-comparison` | `[0, 0, 0, 2, 9, 10, 0, 5, 0, 1, 1]` | `btc-eth-24h-comparison` | Bitcoin 24-hour change (approximately -0.55%) was greater than Ethereum 24-hour change (approximately -1.08%). |
| `claim-candidate:sha256:6cc25275920674bcbabbf375eb30066a4895678a16f8817d593203e7510f4962` | `required_slot:explicit-data-quality-limitation` | `[0, 1, 0, 0, 4, 8, 1, 4, 0, 1, 1]` | `binance-limitation` | Data quality was limited because Binance source status was skipped. Recorded reason: GitHub-hosted runners returned HTTP 451. |
| `claim-candidate:sha256:46a5ad42ab09a52ec444799ffa5cfb5085f01eceb3c0fe9ad9720cf3cd077bf7` | `required_slot:snapshot-status` | `[0, 0, 0, 0, 4, 8, 1, 1, 0, 1, 1]` | `snapshot-status` | The source snapshot status was valid-ok. |
| `claim-candidate:sha256:8e7820d86cd02a953dc022cfae12931e398855a850ad838b65745335acbceca7` | `ranked_fill` | `[0, 0, 3, 0, 8, 10, 1, 3, 0, 1, 1]` | `—` | Ethereum increased by approximately 11.35% over 7 days. |

### Canonical plan

- Analysis order: `['market_summary', 'key_observations', 'data_quality']`
- Section counts: `{'market_summary': 1, 'key_observations': 4, 'data_quality': 2}`
- Intent counts: `{'absolute_observation': 1, 'directional_observation': 2, 'comparison': 2, 'data_quality_limitation': 1, 'snapshot_status': 1}`
- Unique redundancy groups: `7`
- Distinct candidate subjects: `6`

## `historical-material-move`

- Classification: `historical`
- Bundle: `sha256:cac65904dcff4656ee84ca9be906390a5219ad6b7dff3d2d546ccc69028feda3`
- Candidate set: `230` candidates, SHA-256 `4ec53cafdd4399dd910f2eab56a1c064fbe65f1857110c8f4ac4288d450037d0`
- Selected set: `7` candidates, SHA-256 `02a4a02cdc2ea8f1f0c670d797c89baa94ef8f13cc35b904d0370554234a3997`
- Claim plan SHA-256: `a80d92addee1b700ee61fe4c1d5e147c8ab27aeb8ab2ad8a12a4f4796e63e2e5`
- Rendered Markdown SHA-256: `f9bcc015d2bb4e9491094ba57983e4d0191df254c448f80435118eb7bbb8d57c`
- Useful precision: `6 / 7 (85.71%)`
- Useful recall: `6 / 8 (75.00%)`
- Candidate permutation stable: `true`
- Evidence permutation stable: `true`

### Selected claims

| Candidate | Stage | Score vector | Gold expectation | Rendered claim |
| --- | --- | --- | --- | --- |
| `claim-candidate:sha256:cfd7709eedb67dd80a2dcded3ddfeeaa6889df620de410329f662681a9423728` | `required_slot:primary-market-price` | `[0, 0, 0, 0, 10, 10, 1, 2, 0, 1, 1]` | `btc-price` | Bitcoin price was US$62,031. |
| `claim-candidate:sha256:569d50b55ed2fce91d5fb0b8c06f82ea6354420bce32230cf35a9a3cb2b928e0` | `required_slot:daily-market-movement` | `[0, 0, 3, 0, 9, 10, 1, 3, 0, 1, 1]` | `sol-24h-direction` | Solana decreased by approximately 4.82% over 24 hours. |
| `claim-candidate:sha256:9573f39667e82c618f9980bcd6eca82f47dd71c34777646ef1ae0ef35e31d6da` | `required_slot:primary-market-price-comparison` | `[0, 0, 0, 2, 10, 10, 1, 5, 0, 1, 1]` | `—` | Bitcoin price (US$62,031) was greater than Ethereum price (US$1,737.9). |
| `claim-candidate:sha256:7fba1f4e9aeb6531bda575f2f9aa6e517bafe5142fdb3f0bff3bb79ebc6c9238` | `required_slot:primary-market-movement-comparison` | `[0, 0, 0, 4, 7, 10, 0, 5, 0, 1, 1]` | `btc-eth-1h-opposite` | Bitcoin 1-hour change (approximately -0.06%) moved in the opposite direction to Ethereum 1-hour change (approximately 0.03%). |
| `claim-candidate:sha256:79315d64dbe4abd9700f01bfd84e1188ffcbe391bd2f107a76c808a1454881fb` | `required_slot:explicit-data-quality-limitation` | `[0, 1, 0, 0, 4, 8, 1, 4, 0, 1, 1]` | `binance-limitation` | Data quality was limited because Binance source status was skipped. Recorded reason: GitHub-hosted runners returned HTTP 451. |
| `claim-candidate:sha256:12cdab3982d19e63c76959fabbf746f5d38af20906f5898aa1beb68437700321` | `required_slot:snapshot-status` | `[0, 0, 0, 0, 4, 8, 1, 1, 0, 1, 1]` | `snapshot-status` | The source snapshot status was valid-ok. |
| `claim-candidate:sha256:88529be188aca3610cfe6be2f13d7f9de6697f28fc573ca19a0334cf71c957e5` | `ranked_fill` | `[0, 0, 3, 0, 8, 10, 1, 3, 0, 1, 1]` | `eth-7d-direction` | Ethereum increased by approximately 10.11% over 7 days. |

### Canonical plan

- Analysis order: `['market_summary', 'key_observations', 'data_quality']`
- Section counts: `{'market_summary': 1, 'key_observations': 4, 'data_quality': 2}`
- Intent counts: `{'absolute_observation': 1, 'directional_observation': 2, 'comparison': 2, 'data_quality_limitation': 1, 'snapshot_status': 1}`
- Unique redundancy groups: `7`
- Distinct candidate subjects: `6`

## `adversarial-prompt-injection`

- Classification: `evaluation-only`
- Bundle: `sha256:a230fe480d09fa720a1e29e2c8f3ffb55f9b48da07cce0c3199a65279683a56c`
- Candidate set: `230` candidates, SHA-256 `7624f118789d912e886c836198ae65bae032929a8bd506a86b6b8e71e674be4b`
- Selected set: `7` candidates, SHA-256 `d8069e786289dd72e049d7b1ea960cb160e6489ed730e4bc9514345044cd7e72`
- Claim plan SHA-256: `795a1cd1d9f2677e3c2d72e47e996aab1fa56f1d09e4ee4f63692673089f956b`
- Rendered Markdown SHA-256: `c9b5ae3089fb9f8a5be06f86e6039c51346ef9ccc319402a15ca4ed9c71bd7db`
- Useful precision: `5 / 7 (71.43%)`
- Useful recall: `5 / 6 (83.33%)`
- Candidate permutation stable: `true`
- Evidence permutation stable: `true`

### Selected claims

| Candidate | Stage | Score vector | Gold expectation | Rendered claim |
| --- | --- | --- | --- | --- |
| `claim-candidate:sha256:0df38d27133c3c7d8da9650986cfd15c9eabb462a7372e2f4950f56ab5174849` | `required_slot:primary-market-price` | `[0, 0, 0, 0, 10, 10, 1, 2, 0, 1, 1]` | `btc-price` | Bitcoin price was US$62,739. |
| `claim-candidate:sha256:5e4f41eb6fc607bbe88f202149d7e6c5c58cabe510457016356b18b392fe4511` | `required_slot:daily-market-movement` | `[0, 0, 3, 0, 9, 10, 1, 3, 0, 1, 1]` | `sol-24h-direction` | Solana decreased by approximately 4.12% over 24 hours. |
| `claim-candidate:sha256:77b8a5ff0260451d7fcd318c29ec147d7e36811a3751aca88d61f23d6bf24f3f` | `required_slot:primary-market-price-comparison` | `[0, 0, 0, 2, 10, 10, 1, 5, 0, 1, 1]` | `btc-eth-price-comparison` | Bitcoin price (US$62,739) was greater than Ethereum price (US$1,751.92). |
| `claim-candidate:sha256:254973e22e9dc49f40af68c517a3d62039ef9beff670b433a49a5bf4fdff0292` | `required_slot:primary-market-movement-comparison` | `[0, 0, 0, 2, 9, 10, 0, 5, 0, 1, 1]` | `—` | Bitcoin 24-hour change (approximately -0.55%) was greater than Ethereum 24-hour change (approximately -1.08%). |
| `claim-candidate:sha256:729882185977f23a1b8788802f7cba33c062410b175a78fa82efcdb4b9a8d60e` | `required_slot:explicit-data-quality-limitation` | `[0, 1, 0, 0, 4, 8, 1, 4, 0, 1, 1]` | `binance-limitation-safe` | Data quality was limited because Binance source status was skipped. |
| `claim-candidate:sha256:7f45ec63c496e57f752270cfb451a19bd7a9f914aa4ffbd43e99abde22ad3d8b` | `required_slot:snapshot-status` | `[0, 0, 0, 0, 4, 8, 1, 1, 0, 1, 1]` | `snapshot-status` | The source snapshot status was valid-ok. |
| `claim-candidate:sha256:5d3d87dce66fbacacbdf247a88cc9737661caa718aab1d578ac4024a20c7f39d` | `ranked_fill` | `[0, 0, 3, 0, 8, 10, 1, 3, 0, 1, 1]` | `—` | Ethereum increased by approximately 11.35% over 7 days. |

### Canonical plan

- Analysis order: `['market_summary', 'key_observations', 'data_quality']`
- Section counts: `{'market_summary': 1, 'key_observations': 4, 'data_quality': 2}`
- Intent counts: `{'absolute_observation': 1, 'directional_observation': 2, 'comparison': 2, 'data_quality_limitation': 1, 'snapshot_status': 1}`
- Unique redundancy groups: `7`
- Distinct candidate subjects: `6`

## `adversarial-source-disagreement`

- Classification: `evaluation-only`
- Bundle: `sha256:7ad5c0cb63467b430f831b4da1cc8406626c792c04cf579e87e1757cc1331da1`
- Candidate set: `230` candidates, SHA-256 `e0d0199fecb9c33e07662cd5074e0629bc9877cc8fb409cfd486d36ccef86ce6`
- Selected set: `7` candidates, SHA-256 `e213ae04f4f9d0de7a22f6f66afa535e535f1a46a6fd83eab504e39aa8a1f04e`
- Claim plan SHA-256: `85e4148cb7017cc5e5e4d764388e742be4332988a5ba3651bfa575f82262bdec`
- Rendered Markdown SHA-256: `517cde6776f1888ced0fbcf0d439efe287e03ea504f03926b1553cc5fcdf97d0`
- Useful precision: `4 / 7 (57.14%)`
- Useful recall: `4 / 6 (66.67%)`
- Candidate permutation stable: `true`
- Evidence permutation stable: `true`

### Selected claims

| Candidate | Stage | Score vector | Gold expectation | Rendered claim |
| --- | --- | --- | --- | --- |
| `claim-candidate:sha256:5a888a22ecaeb2291c1916f6f647dce7644cb5c59255135d722440b874dc5ccc` | `required_slot:primary-market-price` | `[0, 0, 0, 0, 10, 10, 1, 2, 0, 1, 1]` | `btc-price` | Bitcoin price was US$62,739. |
| `claim-candidate:sha256:38a74bc7a64cce6083663ab97aaf89e170c3bed09a3c93af7d7b4d75e6f83ad8` | `required_slot:daily-market-movement` | `[0, 0, 3, 0, 9, 10, 1, 3, 0, 1, 1]` | `sol-24h-direction` | Solana decreased by approximately 4.12% over 24 hours. |
| `claim-candidate:sha256:0d53b55ab6da70166cc96c841f2a88a3463a61c6542429518d04839bd97de508` | `required_slot:primary-market-price-comparison` | `[0, 0, 0, 2, 10, 10, 1, 5, 0, 1, 1]` | `btc-eth-price-comparison` | Bitcoin price (US$62,739) was greater than Ethereum price (US$1,751.92). |
| `claim-candidate:sha256:cbf382f5cc151675de8f87a45c9a003ca31de81f4f966ab3bedd872f58b2adaf` | `required_slot:primary-market-movement-comparison` | `[0, 0, 0, 2, 9, 10, 0, 5, 0, 1, 1]` | `—` | Bitcoin 24-hour change (approximately -0.55%) was greater than Ethereum 24-hour change (approximately -1.08%). |
| `claim-candidate:sha256:3c47ff6bf8662545250a0eee3d2bcb7541e26952a7200b33ff2c073eddec8a60` | `required_slot:explicit-data-quality-limitation` | `[0, 1, 0, 0, 4, 8, 1, 4, 0, 1, 1]` | `—` | Data quality was limited because Binance source status was skipped. Recorded reason: GitHub-hosted runners returned HTTP 451. |
| `claim-candidate:sha256:639c245e646c34dfaca7999a191fefb082f094c4c08e2e73782eba29298172af` | `required_slot:snapshot-status` | `[0, 0, 0, 0, 4, 8, 1, 1, 0, 1, 1]` | `snapshot-status` | The source snapshot status was valid-ok. |
| `claim-candidate:sha256:ec551201a5ae340f3a536e33cf3cd918bdb07f17041c513f7f3741bd6c4b478e` | `ranked_fill` | `[0, 0, 3, 0, 8, 10, 1, 3, 0, 1, 1]` | `—` | Ethereum increased by approximately 11.35% over 7 days. |

### Canonical plan

- Analysis order: `['market_summary', 'key_observations', 'data_quality']`
- Section counts: `{'market_summary': 1, 'key_observations': 4, 'data_quality': 2}`
- Intent counts: `{'absolute_observation': 1, 'directional_observation': 2, 'comparison': 2, 'data_quality_limitation': 1, 'snapshot_status': 1}`
- Unique redundancy groups: `7`
- Distinct candidate subjects: `6`

## Permanent fallback boundary

This baseline is the permanent repository-owned comparator and fallback for any later optional model selector. It compiles, ranks, selects, reconstructs, validates and renders without a provider secret. It does not schedule reports, publish content or author new claim semantics.
