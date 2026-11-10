You are helping me archive a newly generated crypto market intelligence report above

Repo:

`8ft0-ai/crypto-pulse`

Task:

Upload the provided Markdown report to the correct archive path in the GitHub repo and commit it directly to `main`.

Do not regenerate or rewrite the report unless required only to add missing YAML front matter. Preserve the report body exactly as provided.

## Required archive path

Save hourly reports here:

`reports/crypto/hourly/YYYY/MM/DD/HHMM_TZ_crypto_market_intelligence.md`

Examples:

`reports/crypto/hourly/2026/05/09/1848_AEST_crypto_market_intelligence.md`

`reports/crypto/hourly/2026/10/04/0930_AEDT_crypto_market_intelligence.md`

Use the report’s own timestamp to determine:

- year;
- month;
- day;
- hour;
- minute;
- timezone abbreviation.

If the report timestamp is in Sydney time, use `AEST` or `AEDT` as appropriate.

## Timestamp priority

Determine the report timestamp in this order:

1. YAML front matter field: `timestamp`
2. Report header line such as `Report timestamp:`
3. Data cut-off time if no report timestamp exists
4. Ask me only if no timestamp can be found

Do not use the current time unless the report clearly has no timestamp and I explicitly approve.

## YAML front matter

If the report does not already contain YAML front matter, prepend this format using the detected timestamp:

```yaml
---
report_type: hourly_crypto_market_intelligence
timestamp: YYYY-MM-DD HH:MM TZ
data_cutoff: YYYY-MM-DD HH:MM TZ
live_data_status: partial
primary_assets:
  - BTC
  - ETH
  - SOL
  - XRP
  - BNB
tags:
  - crypto
  - hourly-report
  - market-intelligence
  - trading
---
```

If front matter already exists, preserve it unless it is clearly missing `report_type`.

## GitHub workflow

1. Read the provided report from the message or uploaded file.
2. Confirm the destination path.
3. Check whether the file already exists.
4. If it does not exist, create it.
5. If it exists with identical content, do not commit a duplicate.
6. If it exists but differs, update it only if the new report appears to be the corrected version of the same timestamped report.
7. Commit directly to `main`.

Commit message format:

`Add hourly crypto report YYYY-MM-DD HHMM TZ`

For an update:

`Update hourly crypto report YYYY-MM-DD HHMM TZ`

## Final response

After committing, reply with:

- the file path;
- the commit SHA;
- whether the file was created, updated, or unchanged.

Do not open a PR.
