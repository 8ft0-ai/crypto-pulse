# Phase 5 historical model evaluation

This directory defines the fixed inputs and scoring rules for issue #188. It does not contain provider output and does not make a model-selection claim before controlled runs exist.

## Fixed corpus

The corpus contains three immutable historical snapshots and two deterministic evaluation-only mutations:

- a valid-degraded legacy snapshot with sparse optional exchange evidence;
- a normal valid-ok cross-checked snapshot;
- a valid-ok snapshot with materially different short- and seven-day movements;
- a prompt-injection probe derived from the normal snapshot; and
- a synthetic source-disagreement probe derived from the normal snapshot.

The two mutations are deliberately labelled `evaluation-only`. They are not historical facts, are not report inputs and are never reused as evidence.

## Bounded comparison

The source-controlled comparison contains exactly two explicit free model slugs: the current Nemotron candidate and one Qwen alternative. `openrouter/free`, `openrouter/auto`, paid models and cross-model fallback are prohibited.

At execution time the workflow checks the public OpenRouter catalogue again. A disappeared, expired, non-zero-price or structured-output-ineligible model is recorded as ineligible rather than silently replaced.

## Operating sequence

```text
merge evaluation harness
manually dispatch Governed LLM model evaluation from main
review evaluation artefacts and reviewer worksheet
commit the approved retain/change/no-go decision in a separate review PR
```

The separate decision PR is required because pull-request code must not receive `OPENROUTER_API_KEY`, and workflow artefacts must be reviewed before a production-proof configuration is selected.
