# Phase 8 observable OpenRouter transport calibration

This directory records the source-controlled contract for issue #325. Provider responses remain protected GitHub Actions artifacts and are not committed here.

## Question

> Can at least one model complete the real candidate-ID request under an observable, realistically configured route?

## Fixed execution

The experiment regenerates `historical-degraded-sparse` from trusted repository inputs and sends the complete compact projection of all 201 candidates. The response remains the existing one-field `selected_candidate_ids` envelope, with repository-owned validation, reconstruction and rendering.

There is no preliminary generated route probe.

Stage A allows OpenRouter to select an eligible provider while preserving `require_parameters: true`, `data_collection: deny`, strict JSON Schema, a preferred provider order and complete router metadata. Stage B pins the provider observed in the first successful discovery and repeats the real request once with fallbacks disabled.

## Candidates

```text
inception/mercury-2
openai/gpt-oss-120b
```

## Limits

```text
discovery calls:       2 maximum
reproduction calls:    1 maximum
paid calls:            3 maximum
per-call cost:         USD 0.025 maximum
whole cost:            USD 0.060 maximum
max output tokens:     2,048
reasoning effort:      minimal
semantic repairs:      0
network retries:       0
```

## Interpretation

A successful discovery and reproduction answers the transport question **yes**. It does not establish candidate-selection quality, repeat stability, incremental value or production suitability.

A failure is classified at the transport, HTTP, metering, cost, identity, router-metadata, provider-slug, response-shape, content, JSON, candidate-validation or reconstruction boundary. Model quality is not inferred from failures before a valid candidate envelope completes.

## Governance

The workflow is manual, trusted-main, read-only and protected by `governed-llm-dry-run`. It cannot write repository state, generate a production report or publish the site. After the single authorised run, the workflow must be archived and a separate Phase 8 decision committed.