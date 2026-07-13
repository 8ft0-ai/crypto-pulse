# Semantic claim-plan model selection

This directory defines the Stage 1 evaluation requested by issue #263. It compares two affordable production candidates with GPT-5.6 Sol as a benchmark-only quality reference.

## Candidate roles

- `openai/gpt-5.6-sol` establishes the quality ceiling and is excluded from deployment selection.
- `nex-agi/nex-n2-mini` is the primary affordable candidate.
- `minimax/minimax-m3` is the consistency candidate.
- `cohere/north-mini-code:free` is retained only as catalogue evidence because the current listing does not advertise the strict structured-output parameters required by CryptoPulse.

The workflow checks the live catalogue and exact route again. No unavailable or ineligible model is silently replaced.

## Frozen corpus

The evaluation reuses the existing five-case semantic claim-plan corpus without changing historical snapshots, mutations or SHA-256 locks:

- degraded and sparse historical data;
- normal cross-checked historical data;
- a historical material-move case;
- an evaluation-only prompt-injection case;
- an evaluation-only source-disagreement case.

`expectations.yml` adds case-specific semantic checks without requiring one exact JSON plan. It distinguishes hard semantic misses from softer materiality and restraint deductions.

## Operating sequence

1. Merge the evaluation harness.
2. Manually dispatch **Governed semantic plan model selection** from trusted `main`.
3. Review retained provider, validation, rendering, cost and leaderboard artefacts.
4. Record a separate reviewed Stage 1 decision.
5. Advance at most two affordable finalists to a broader hidden corpus.

The workflow is read-only and artefact-only. It cannot publish analysis, push a branch or update a report.
