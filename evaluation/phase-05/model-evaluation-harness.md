# Governed LLM model evaluation

Issue #188 uses a protected, artefact-only workflow to compare a small fixed model set over a locked historical corpus. It deliberately does not let pull-request code receive the provider secret and does not commit provider output automatically.

## Trust and secret boundary

The workflow must be dispatched from `main`. A secret-free job checks out current `main`, validates the SHA-256 locks for every historical snapshot and creates deterministic evidence bundles. The protected job then checks out that exact commit and uses the existing `governed-llm-dry-run` environment.

`OPENROUTER_API_KEY` is present only on the single evaluation command. Checkout credentials are not persisted, repository permissions are read-only, and the workflow cannot push a branch, open a pull request, deploy or publish.

## Current bounded candidates

The checked-in plan compares:

```text
current candidate: nvidia/nemotron-3-super-120b-a12b:free
alternative:       qwen/qwen3-next-80b-a3b-instruct:free
```

The workflow checks the live OpenRouter catalogue before generation. Both prompt and completion prices must still be zero, and both `response_format` and `structured_outputs` must still be supported. A missing, expired or changed listing becomes an explicit ineligible result; it is never replaced by `openrouter/free`, `openrouter/auto` or another model.

## Corpus boundary

Three cases are immutable archived source snapshots. Two cases are deterministic mutations of the locked normal bundle for prompt-injection and source-disagreement testing. Mutations are recorded in the prepared manifest and input bundle hash. They are evaluation-only and cannot be promoted by the rolling report workflow.

## Hard and soft evaluation

Any schema, evidence, numeric, semantic, policy, prompt-injection, routing or generation failure disqualifies that model configuration. Soft usefulness and readability proxies are calculated only after acceptance. Two repeats per case provide a simple exact-output reproducibility signal.

The workflow emits raw completions, accepted JSON where available, validation reports, generation metadata, model availability, aggregate scoring, a reviewer worksheet and a decision candidate. These are retained as workflow artefacts for review, not published content.

## Completing #188

After the harness is merged, manually run **Governed LLM model evaluation** from `main`. Review the artefact bundle, complete or annotate the reviewer worksheet, and commit one approved `retain`, `change` or `no-go` decision record. The harness PR intentionally does not close #188 before that evidence exists.
