# Stage 4B daily evidence and Stage 4C cutover preparation

Stage 4B's manual daily generation, immutable attestation and independent
read-only gate were accepted in November 2026. The Stage 4C integration
prepares a scheduled generator and independently authorised merge route,
but **neither is activated by merging this code**. Hourly source ingestion
and hourly publication remain unchanged until separately authorised cutover.

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

The workflow `.github/workflows/generate-daily-crypto-report.yml`
accepts a manually selected UTC reporting date, or, once Stage 4C recurring
activation is separately authorised, selects the previous UTC day at the
prepared 01:17 UTC schedule (after the immutable D+1 01:00 UTC cut-off).
The scheduled job is **skipped** unless repository variable
`CRYPTO_DAILY_PROMOTION_MODE` is explicitly set to `enabled`.
The workflow validates source eligibility and duplicates, replays the
deterministic report, creates one App-authored draft review PR named
`automation/daily-publication-<run>-<attempt>-<date>` and uploads an
immutable `cryptopulse-daily-attestation-<run>-<attempt>` artefact.
Manual generation remains available with the promotion mode unset.

Daily candidate PRs use a separate read-only `daily-preflight` job in the
existing publication gate. Its independent GO output is required for the
separately gated `daily-merge` job. The hourly `preflight` and `merge`
jobs, their provenance rules and their permissions are unchanged.

`scripts/daily_publication.py` owns the separate
`cryptopulse-daily-publication/v1` / `daily-review-pr/v1` contract. Its
attestation binds the date and cutoff, trusted source and expected main base,
all 24 slot dispositions and source paths/digests, population digest, report
path/digest, branch/head, PR, generation run and publication App identity.
`scripts/deterministic_site_publication.py daily-gate-preflight` evaluates
daily facts independently. The existing hourly validation and merge contract
is unchanged.

The daily merge job is fail-closed by default because
`CRYPTO_DAILY_PROMOTION_MODE` is unset. It has two separately authorised modes:

- `pilot`: permit only one explicitly pre-armed, already independently
  eligible **manual** candidate, matching all four repository variables:
  `CRYPTO_DAILY_PROMOTION_PILOT_PR_NUMBER`,
  `CRYPTO_DAILY_PROMOTION_PILOT_HEAD_SHA`,
  `CRYPTO_DAILY_PROMOTION_PILOT_BASE_SHA` and
  `CRYPTO_DAILY_PROMOTION_PILOT_RUN_ID`.
  This permits one SHA-bound live promotion only after owner authorisation.
- `enabled`: permit separately authorised **scheduled** candidates only.
  No manually dispatched candidate may be automatically merged in this mode.

The daily merge job rechecks the exact candidate head and the current
protected-main SHA before App-token minting, marks the draft candidate ready
and rechecks both identities before the SHA-bound merge. Any missing pin,
changed base/head, duplicate, failed CI or independent gate failure stops the
promotion. It reuses the existing GitHub App and
`deterministic-publication-control` environment; no additional secret,
scheduler service or deploy path is introduced.

## Stage 4B live acceptance and Stage 4C production boundary

Stage 4B's non-publishing live pilot produced App-authored draft PR #773 for
22 November 2026 UTC (generation run #45523027956, candidate validation
#45523100564 and independent read-only gate #45523649167). The gate returned
GO, while its privileged merge jobs were correctly skipped. The report digest
was `44c042545b82c146284ba481f5c72abce464a778e7242178e9d8a9be1b744ab4`.
No daily report was promoted to protected main. Its original base is stale;
do not treat the older accepted attestation as current merge authority.

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

The Stage 4C code prepares a route through the existing gate, but this
code-only PR does not authorise or perform a live publication. A fresh,
current-main-bound candidate and independently successful read-only gate,
explicit pilot-mode promotion authorisation, protected-main readback and
external Pages verification are required before the first live report is
accepted. The source ingestion pipeline and archived hourly URLs remain intact.

For an authorised future cutover: keep the existing hourly workflow definition
revertible; verify the first daily protected-main merge and integrated Pages
delivery; confirm subsequent ingestion and durable source recovery; roll back
by re-enabling the previous hourly publication trigger and disabling daily
publication. Never rewind protected main or rewrite historical report files.

## Stage 4C source-continuity prerequisite for retiring hourly reports

The earlier hourly publication gate merges **both** the validated source JSON
and its hourly Markdown report. Simply disabling that workflow stops updates
to trusted-main source evidence; the accepted-hour receipts and rolling source
PR are not themselves on protected main. A daily report would then eventually
disclose 24 missing hours, despite successful external ingestion.

Stage 4C therefore adds an opt-in, source-only job to the **existing hourly
ingestion workflow**, with no extra scheduler:

- `CRYPTO_SOURCE_PROMOTION_MODE` is **unset/disabled by default**. When set to
  `enabled`, successful hourly ingestion still uploads its accepted-hour
  receipt and immutable source intent but skips updating the rolling inspection
  PR. An isolated job receives the existing protected publication environment.
- The job independently validates the original source-run identity, receipt,
  intent, exact snapshot SHA-256, UTC hour, source quality and pinned config
  before minting the existing publication App token. This is not a replacement
  market-data source.
- It creates one **App-authored, one-JSON-file** draft PR from the current main,
  requires separate exact-head GitHub CI success from `github-actions`,
  rechecks exact main/head/PR scope and uses the existing App for a protected
  SHA-bound merge. Immutable output proof is retained as an Actions artefact.
  If main advances, CI fails or source bytes disagree, the promotion stops
  without rewriting evidence. Duplicate identical source bytes are idempotent.
- The existing hourly and daily publication gate workflows still verify their
  original candidate types. A source-only PR is excluded from the irrelevant
  publication gate trigger; it uses its own immutable receipt validation and
  separately executed GitHub PR CI.
- Neither the hourly ingestion job nor the source-only job generates hourly
  Markdown when source-only mode is enabled. Existing published hourly archive
  files and URLs remain untouched.

**Protected cutover order:** merge and independently review this dormant code;
activate source-only mode; verify a genuine ingestion-run source-only PR,
CI, source digest and protected-main commit. Only after that acceptance may the
old hourly generator be disabled (reversible GitHub workflow state) and
`DETERMINISTIC_PUBLICATION_ACTIVATION` set to `disabled`. Keep the independently
activated daily generator. Verify the next scheduled daily report has continued
trusted-main source coverage and passes its read-only gate and public Pages
check. Never infer 30-day coverage or workflow savings from configuration alone.

**Rollback:** Set `CRYPTO_SOURCE_PROMOTION_MODE` back to `disabled`, re-enable
the unchanged hourly generator and restore
`DETERMINISTIC_PUBLICATION_ACTIVATION=recurring` after rechecking main and
avoiding an overlapping source-only/legacy merge. Do not rewind main or delete
archived reports. Measure a full post-cutover 24-hour window before claiming
workflow-run savings.
