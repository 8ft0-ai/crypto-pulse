# Stage 4A — one-off retrospective source recovery

This command recovers the **exact 25 observations** selected in [PR #668](https://github.com/8ft0-ai/crypto-pulse/pull/668). It is separate from, and does not modify, the forward-only trusted-main accumulation path.

The explicit input is `tests/fixtures/stage4a_pr668_source_set.json`. Obtain the retained evidence bundle from GitHub Actions run `44846754594`, attempt 1, artifact `trusted-main-source-evidence-candidate-44846754594-1`. Fetch the original candidate commit `4d7562d443c2164b01d63bb70e7f338c76a4ee41` and the snapshot commits referenced by the original publication intents into the local Git object store. No source reconstruction is permitted.

Run only against an **exact, freshly checked protected-main commit**:

```sh
python scripts/trusted_main_historical_gap_recovery.py \\
  --repository-root . \\
  --trusted-main-sha "$EXACT_MAIN_SHA" \\
  --original-candidate-sha 4d7562d443c2164b01d63bb70e7f338c76a4ee41 \\
  --source-set tests/fixtures/stage4a_pr668_source_set.json \\
  --original-bundle "$ORIGINAL_ARTIFACT_DIRECTORY" \\
  --output-directory "$EMPTY_EVIDENCE_DIRECTORY"
```

The command checks remote main at the beginning and end; rejects changed/absent source objects, changed original evidence digests, unverifiable accepted-hour provenance, invalid Phase 12 quality, duplicate hours/paths, and same-path differing trusted bytes. It records already-trusted identical paths idempotently. It emits a new source-population closure and candidate manifest bound to the requested main SHA. For source-only staging, pass `--materialise-to "$EMPTY_SOURCE_ONLY_WORKTREE"` and verify the staged diff with the existing `trusted_main_source_evidence_candidate.py verify-worktree` command.

The exact 24 November 2026 reconstruction manifest and closure are committed under `evidence/stage4a-pr668/`. The original PR and its retained source objects remain historical evidence. The resulting source-only candidate requires exact-head CI, independent review, and a separately authorised protected-main promotion. **Do not merge** either PR as part of this recovery, and do not change PR #730 or reporting cadence.
