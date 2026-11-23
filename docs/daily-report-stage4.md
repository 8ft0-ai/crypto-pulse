# Stage 4 daily evidence candidate (offline only)

This is a dormant, deterministic daily reporting feature. It does not schedule,
publish, merge, or change production ingestion. Hourly reports remain unchanged.

## Frozen UTC-day contract

- Reporting window: UTC date D at 00:00 (inclusive) through D+1 at 00:00
  (exclusive), exactly 24 observation-hour slots.
- Evidence cut-off: D+1 at 01:00 UTC, fixed independently of execution time.
- Source of trust: one exact commit proven to be on protected main by that
  cut-off. Unmerged PR branches and ephemeral GitHub artefacts are excluded.
- Source quality rules: the source-quality config and source bytes are read
  from the exact Git commit, with exact SHA-256 per observation. Inconsistent
  duplicate UTC hours cause a hard failure.
- Output: reports/crypto/daily/YYYY/MM/DD/YYYY-MM-DD_UTC.md. A repeat with
  identical inputs is byte-identical. A conflicting existing report is refused.
- Missing, invalid and degraded slots remain explicit. BTC/ETH/SOL comparisons
  use only first/last qualified source prices; no interpolation or historical
  percentile claims are permitted.

## Reproduce a real candidate

For 22 November 2026 the last observed protected-main first-parent commit
before the evidence cut-off is 71fe674ca237f3079c588c1448cbff562a9e1414.

From a checkout with full origin/main history:

    python scripts/generate_crypto_daily_report.py \
      --report-date 2026-11-22 \
      --trusted-main-sha 71fe674ca237f3079c588c1448cbff562a9e1414

    python scripts/validate_crypto_daily_report.py \
      reports/crypto/daily/2026/11/22/2026-11-22_UTC.md

The report is a local candidate; the generator does not push or open a PR.
The Pages site generator recognises daily reports and retains the existing
hourly archive paths, search index, RSS and latest-report behaviour.

## Production dependency and rollback

Historical accumulator PR #668 currently holds 25 verified source-file
candidates not present on protected main. Do not treat them as trusted-main
history until the existing independent review and protected-main promotion
checks pass. Do not remove rolling-source-PR updates solely on the strength
of their Git accessibility. The existing hourly publication process is still
the mechanism placing current accepted observations durably on protected main.

Before daily cadence activation, the authorised production implementation
must provide an equivalent, independently verified route from accepted-hour
receipts to durable hourly evidence and exactly one daily report candidate
through the existing privileged protected-main gate. All existing archived
hourly URLs must remain intact. No automatic cutover is part of this feature.

For an authorised future cutover: keep the existing hourly workflow definition
revertible; verify the first daily protected-main merge and integrated Pages
delivery; confirm subsequent ingestion and durable source recovery; roll back
by re-enabling the previous hourly publication trigger and disabling daily
publication. Never rewind protected main or rewrite historical report files.
