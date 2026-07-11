# Governed OpenRouter client

Status: implementation record for issue #185.

This module provides the optional provider boundary for Phase 5. It can submit one curated evidence bundle to one explicitly pinned OpenRouter model and return structured analysis plus generation provenance. It does not validate claims, render Markdown, create branches, open pull requests, publish reports, or schedule generation. Those responsibilities remain separate.

## Reviewer-visible configuration

Generation policy lives in:

```text
config/llm-generation.yml
```

The initial proof configuration pins:

```text
provider: openrouter
model: nvidia/nemotron-3-super-120b-a12b:free
prompt: crypto-market-analysis/v1
analysis schema: crypto-market-analysis/v1
evidence schema: crypto-market-evidence-bundle/v1
cross-model fallback: false
```

This is a provisional proof pin, not the Phase 5 model-selection conclusion. Issue #188 owns the historical evaluation corpus and final pinned-model decision.

The configuration rejects `openrouter/free`, `openrouter/auto`, any other OpenRouter router alias, multiple-model routing, weakened privacy settings, unbounded retries, non-HTTPS endpoints, path traversal, unknown keys, and cross-model fallback.

## Request boundary

`llm_analysis/openrouter_client.py` constructs one non-streaming chat-completions request containing:

```text
one singular model slug
one versioned prompt with one canonical evidence bundle inserted between untrusted-data markers
strict response_format=json_schema
reviewer-visible temperature and maximum output tokens
provider policy copied from configuration
no tools
no plugins
no browsing
no secondary models
no route=fallback
```

The client sends `X-OpenRouter-Metadata: enabled` so successful responses can expose selected-provider and fallback-attempt evidence. It uses the OpenRouter fields documented for provider routing and structured output:

```text
provider.require_parameters
provider.data_collection
provider.zdr
provider.allow_fallbacks
provider.order / only / ignore where configured
provider.sort
provider.max_price
response_format.type=json_schema
response_format.json_schema.strict=true
```

Official references:

- https://openrouter.ai/docs/guides/routing/provider-selection
- https://openrouter.ai/docs/guides/features/structured-outputs
- https://openrouter.ai/docs/guides/features/router-metadata
- https://openrouter.ai/docs/api/reference/overview

## Provider and privacy policy

The initial proof requires:

```text
require_parameters: true
data_collection: deny
zdr: true
allow_fallbacks: true
max provider prompt price: 0 USD per million tokens
max provider completion price: 0 USD per million tokens
max provider request price: 0 USD
```

`allow_fallbacks: true` permits OpenRouter to retry eligible providers serving the same pinned model. The request uses only `model`, never `models`, and the client rejects a response whose actual base model differs from the configured base model. Provider fallback is recorded; cross-model fallback remains false.

Strict privacy filtering may leave no eligible provider for the pinned model. That is an expected fail-closed outcome, reported as `ineligible_routing`; the client does not relax ZDR or data-collection policy to obtain a completion.

## Secret handling

`OPENROUTER_API_KEY` is read only from an explicitly supplied value or the process environment. A missing or malformed value fails before the transport is called.

The key is used only in:

```text
Authorization: Bearer <secret>
```

It is not included in:

- prompt text;
- evidence bundles;
- request bodies;
- response artefacts;
- provenance;
- request summaries;
- exception messages;
- logs produced by this module.

The implementation does not expose complete request headers through its result object.

## Bounded execution

Reviewer-visible limits include:

```text
timeout: 60 seconds
retry limit: 1
retry backoff: 1 second
maximum request size: 262,144 bytes
maximum output: 4,000 tokens
maximum accepted response cost: 0.01 USD
```

Only timeout, rate-limit, and selected transient server/provider statuses are retried. The total number of transport attempts is always `retry_limit + 1`. Authentication, billing, privacy/routing, malformed-response, model-mismatch, input-size, and cost-limit failures do not enter an uncontrolled retry loop.

The provider-side zero-price cap prevents paid endpoints from being selected. The response-side cost limit is a second fail-closed check over returned usage metadata; it is not a substitute for the provider-side cap.

## Typed failure categories

The client exposes stable exception classes for:

```text
missing_secret
input_limit
timeout
transport_error
authentication_error
billing_error
provider_error
invalid_response
ineligible_routing
cost_limit
```

Provider error text is whitespace-normalised, length-bounded, and scrubbed of the active API key before it is surfaced.

## Metadata and provenance

A successful result records, where available:

- requested and actual model;
- selected provider;
- generation ID;
- prompt, completion, and total token usage;
- returned cost;
- measured client latency;
- finish reason;
- router attempt number;
- same-model provider fallback status;
- configured provider preferences.

The client also builds a `crypto-market-generation-provenance/v1` object containing the source-snapshot path and hash, evidence-bundle ID and hash, prompt and completion hashes, generation parameters, usage, provider/model identity, routing status, generation ID, timestamp, and cost.

A provider may omit router metadata, for example on a cache replay. In that case `actual_provider` remains `null`; the client does not invent one. The later workflow may retain the raw response as an artefact, but issue #187 decides which accepted records are committed.

## Separation from offline governance

A successful HTTP response is not accepted market analysis. The returned analysis object must still pass the offline pipeline delivered by #184:

```text
schema
referential
value
semantic
policy
deterministic rendering
```

The client deliberately does not call `process_analysis`, because issue #186 will compose provider generation and offline validation in the manual artefact-only workflow.

## Preserved boundaries

```text
No GitHub Actions workflow.
No report branch or pull request creation.
No publication.
No model bake-off.
No scheduled generation.
No cross-model fallback.
No LLM data collection or browsing.
No LLM-authored Markdown.
No committed _site output.
```
