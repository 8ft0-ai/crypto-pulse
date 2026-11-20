# Candidate-only scheduled-source temporal admissibility — v1

Status: bounded implementation contract for CryptoPulse issue [#665](https://github.com/8ft0-ai/crypto-pulse/issues/665), owner instruction to proceed on 20 November 2026, recorded in [#665 comment 7029221749](https://github.com/8ft0-ai/crypto-pulse/issues/665#issuecomment-7029221749). Subject to exact-head CI, independent technical/security review and a separate owner merge decision.

## Authority and scope

This is a **candidate eligibility rule**, not an amendment to the frozen `phase12-observation-hour/v1` validator and not authority to reconstruct missing evidence. The existing Phase 17 `trusted-main-source-evidence-accumulation/v1.1` owner recovery contract remains unchanged. The v1.2 selection policy continues to choose the earliest at most 25 genuine verified observations after the exact protected-main anchor, without interpolation, inference or automatic merges.

The remaining head-of-line problem is that some completed, historical scheduled jobs have unavailable original publication-intent bytes. Their Phase-12 observation hour is not knowable. Their mere creation/run ID may not be used to skip verification.

## Bounded eligibility policy

For a successful scheduled source whose source head has **all** the approved historical producer, validator and ingestion-workflow Git blob identities below, and whose **exact attempt** has a single successful completed ingestion job, the candidate-only latest admissible generation time is:

```
end_time = GitHub Actions exact attempt-specific ingestion job.completed_at
latest_admissible_generated_at = end_time + 24 hours
latest_admissible_observation_hour =
    containing UTC hour of latest_admissible_generated_at
```

The 24-hour allowance is a conservative **policy ceiling**, not an observed clock-sync error bound. If an exactly validated snapshot's `run.generated_at_utc` exceeds that ceiling, it is an input-level hard blocker; the snapshot cannot be promoted. No other constraint on the frozen Phase-12 observation-hour semantics is relaxed.

A successful scheduled input with unavailable exact snapshot or intent bytes is a nonblocking **historical candidate-ineligible diagnostic** only if the independently proven `latest_admissible_observation_hour <= H_main`. This asserts neither the original timestamp nor its actual observation hour. The same bytes remain absent, no fallback/synthetic timestamp is created and no recovery decision is manufactured.

If the job proof, source head, ordered successful generation/validation steps, exact attempt identity, candidate base/anchor, latest rerun or completion time cannot be verified, the original input hard blocker remains. A future-dated timestamp in exact bytes cannot pass the new admission ceiling.

## Approved historical code identities

These are **Git blob SHA-1 identities**, not run ID or source commit allowlists:

| Git path | Allowed blob SHA-1 |
| --- | --- |
| `.github/workflows/ingest-crypto-sources.yml` | `fa3962d2c24c0650070eea798a159493b50ecaaa` or `b23c2854e01073ed9022305e4b881ac4e1dc2613` |
| `scripts/ingest_crypto_sources.py` | `3ef984a7db5e5c5edae1137b14b3cec0e56165f4` |
| `scripts/validate_crypto_observation_hour.py` | `21e18835c1047243ebda4b5ec7760fd9df793356` |

The original workflow, producer and validator blobs were independently checked at `cbaac787015cce6ecf9d2f07bba4a603d3f0f4c2`, `1f4ea6f3e43d80f56d3b029c2be22132f9df800e`, `73bdcddf1f076790de8b65a9e9e99d730e3b0ddb` and `6b73f1d6592547c46189df37bd9f0af0f293bbef`. The second approved workflow blob was inspected at `c4ebf6680ae9a6281b500a46f5ed5cbfdd6be625`: its added scheduler request and accepted-hour receipt stages do not override the identical source-generation command or its observation-hour validator. The producer uses `datetime.now(timezone.utc)` without a `--now` override in this scheduled workflow. The validator requires the canonical observation hour to equal the containing hour of the exact snapshot generation timestamp.

**Future source/ingestion semantics change:** no automatic extension of this approval. Unsupported blob identities fail closed. A fresh bounded owner-reviewed policy/code amendment is necessary to permit historical-ineligibility classification for a changed producer/workflow/validator. This does not prohibit existing exact-byte verification/recovery under the separate governing contract.

## Capture, proof and deterministic replay

Both initial preparation and the final pre-push census must independently query GitHub for the exact `actions/runs/{run_id}/attempts/{attempt}/jobs` record. The candidate verifier checks the job ID, attempt, head, status, conclusion and completed time; requires both `Fetch source data` and `Validate observation hour` to have succeeded inside that job; and refuses duplicates or ambiguous metadata.

The complete source-run census is preserved. Candidate-manifest fields `historical_ineligible_source_inputs` and `temporal_admissibility_proofs` bind every decision-critical input identity, job proof digest, job completion bound, approved blob identity and exact `H_main`; both fields are included in deterministic `candidate_id`. Exact-byte source validation and owner recovery decisions continue to use existing verifier/recovery primitives.

The source-only candidate PR must summarise each historical bound with **null canonical observation hour**. Full proofs remain inspectable in the immutable prepared bundle. Identical sources/proofs and exact base reproduce identical manifest, candidate ID and additions. Changed jobs, source revisions, reruns, recovery bodies or completed times invalidate the old closure and require fresh classification.

## Explicitly excluded

No new data source, scheduler, infrastructure, credential, source reconstruction, synthetic snapshot/hour, interpolation, backfill, selected duplicate winner, report/content change, report publication, automated recovery or merge. Protected main remains the sole trusted archive authority. #660 remains a separate read-only 30-day-baseline scientific assessment and is not satisfied by this amendment.
