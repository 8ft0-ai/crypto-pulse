# Stage 4B daily evidence candidate (dormant)

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
hourly archive paths, search index, RSS and latest-report behaviour. The Pages
push filter now includes daily Markdown paths.

## Daily publication interfaces

The manual-only workflow is
`.github/workflows/generate-daily-crypto-report.yml`. It accepts a UTC date,
checks the fixed cut-off and duplicate date, replays the deterministic report,
creates a one-file `automation/daily-publication-<run>-<attempt>-<date>` review
PR using the existing publication App, and uploads one immutable
`cryptopulse-daily-attestation-<run>-<attempt>` artifact. It has no schedule.
Daily candidate PRs use a separate read-only daily-preflight job inside the existing deterministic publication gate; they cannot enter the hourly privileged merge job.

`scripts/daily_publication.py` owns the separate
`cryptopulse-daily-publication/v1` / `daily-review-pr/v1` contract. Its
attestation binds the date and cutoff, trusted source and expected main base,
all 24 slot dispositions and source paths/digests, population digest, report
path/digest, branch/head, PR, generation run and publication App identity.
`scripts/deterministic_site_publication.py daily-gate-preflight` evaluates
daily facts independently. The existing hourly validation and merge contract
is unchanged.

After separately authorised Stage4C work, run the manual workflow from `main`
after D+1 01:00 UTC with the exact date; review the single-file PR and require
the independent daily-preflight job to pass before any separately authorised
promotion. Do not enable a schedule or merge path as part of Stage4B.

## Dormant and unverified boundaries

There has been no workflow dispatch, App-backed daily PR creation, immutable
artifact retrieval, or live daily gate execution as part of Stage 4B. Workflow
dispatch cannot execute the new manual workflow until its definition is merged
onto protected main during separately authorised integration acceptance.

Daily eligibility uses the previously accepted first-parent protected-main
commit as-of the fixed D+1 01:00 UTC cut-off, independently recomputed by the
read-only gate. Exact source blobs, their digests, the quality configuration,
24-slot population and final Markdown bytes are replay-verified. Git timestamp
chronology is not an independently authenticated receipt against deliberately
backdated commit timestamps; this limitation must be assessed before cutover.
The daily-preflight job has no merge permissions or App token.

CryptoPulse is a demo. Daily reports are AI-generated examples and may be
wrong, incomplete, stale or misleading. They are not financial advice,
investment research, recommendations or trading signals, and should not be
used for trading, investing or risk decisions.

## Production dependency and rollback

PR #747 promoted 25 independently reconciled historical source blobs to
protected main and PR #668 was closed without merge. Observations admitted
after the original reporting day cut-off do not retroactively qualify for
that original daily report. This does not qualify a 30-day scientific
baseline. Keep hourly ingestion, hourly publication and rolling source
PR mechanisms in place until separately authorised controlled cutover.

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
