# Governed OpenRouter client

> **Mode:** Reference  
> **Audience:** CryptoPulse developers, reviewers and governance stakeholders  
> **Outcome:** Look up the configured provider request, privacy, routing, secret, retry, cost and provenance controls.

The client submits one curated evidence bundle to one explicitly pinned OpenRouter model and returns structured output plus typed generation metadata. It does not accept claims, render Markdown, write repository files, create pull requests or publish reports.

## Canonical implementation and configuration

| Purpose | Path |
| --- | --- |
| Client implementation | [`llm_analysis/openrouter_client.py`](../../llm_analysis/openrouter_client.py) |
| Configuration parser and validation | [`llm_analysis/generation_config.py`](../../llm_analysis/generation_config.py) |
| Default proof configuration | [`config/llm-generation.yml`](../../config/llm-generation.yml) |
| Versioned prompt | [`prompts/crypto-market-analysis-v1.md`](../../prompts/crypto-market-analysis-v1.md) |
| Structured analysis schema | [`schemas/crypto-market-analysis-v1.json`](../../schemas/crypto-market-analysis-v1.json) |

The checked-in configuration is reviewer-visible and may represent a bounded proof profile rather than an approved production route. Reviewed eligibility and model decisions are recorded separately under [`evaluation/phase-05/`](../../evaluation/phase-05/README.md).

## Request shape

The client creates one non-streaming chat-completions request containing:

```text
one explicit model slug
one versioned prompt
one canonical evidence bundle between untrusted-data markers
strict response_format=json_schema
reviewer-visible temperature and output-token limit
provider policy copied from configuration
no tools
no plugins
no browsing
no secondary models
no cross-model fallback route
```

The request uses the configured HTTPS endpoint. Router aliases such as `openrouter/free` and `openrouter/auto`, multiple-model routing, unknown configuration keys, path traversal, non-HTTPS endpoints and cross-model fallback are rejected.

## Current default limits

The authoritative values are in [`config/llm-generation.yml`](../../config/llm-generation.yml). At the time this reference was written, the default profile specifies:

| Setting | Value |
| --- | ---: |
| Endpoint | `https://openrouter.ai/api/v1/chat/completions` |
| Timeout | 60 seconds |
| Retry limit | 1 |
| Retry backoff | 1 second |
| Maximum request size | 262,144 bytes |
| Maximum output | 4,000 tokens |
| Maximum accepted response cost | USD 0.01 |
| Temperature | 0.2 |
| Structured output | required |
| Cross-model fallback | false |

Configuration is the source of truth when it differs from this descriptive table.

## Provider policy

The default proof profile requires:

```text
require_parameters: true
data_collection: deny
zdr: true
allow_fallbacks: true
provider sort: price
maximum provider prompt price: 0
maximum provider completion price: 0
maximum provider request price: 0
```

`allow_fallbacks: true` permits retries across eligible providers serving the same pinned base model. The request uses a singular `model` field, never a `models` list. A response whose actual base model differs from the configured base model is rejected.

Same-model provider fallback is recorded in provenance. Cross-model fallback remains false.

If no provider satisfies the configured privacy, parameter and price policy, the result is `ineligible_routing`. The client does not relax zero-data retention, data-collection denial, model identity or price limits to obtain a completion.

## Secret handling

The client reads `OPENROUTER_API_KEY` only from an explicitly supplied value or the process environment. A missing or malformed secret fails before the transport call.

The secret is used only in:

```text
Authorization: Bearer <secret>
```

It is excluded from:

- prompt text;
- evidence bundles;
- request bodies;
- response artefacts;
- provenance objects;
- request summaries;
- exception messages;
- module logs;
- complete result-object headers.

The workflow-level isolation of this secret is described in [Trusted main and secret isolation](../explanation/trusted-main-and-secret-isolation.md).

## Retry behaviour

Only bounded transient failures are eligible for retry, including configured timeout, rate-limit and selected server or provider statuses.

The maximum transport attempts are:

```text
retry_limit + 1
```

Authentication, billing, privacy or routing ineligibility, malformed response, model mismatch, input-size and cost-limit failures do not enter an uncontrolled retry loop.

The provider-side price cap prevents paid endpoints from being selected for a zero-price profile. The response-side cost limit independently rejects returned usage metadata above the configured ceiling.

## Typed failure categories

The client exposes stable categories:

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

Provider error text is whitespace-normalised, length-bounded and scrubbed of the active key before being surfaced.

## Response requirements

A successful transport result must contain:

- a completion for the requested base model;
- strict structured output compatible with the requested schema envelope;
- usage and routing metadata where the provider returns them;
- no cost above the configured response ceiling.

Transport success is not analysis acceptance. The returned object still passes the complete [offline validation pipeline](offline-validation-pipeline.md).

## Generation metadata

A successful result records available values for:

```text
requested model
actual model
selected provider
generation identifier
prompt tokens
completion tokens
total tokens
returned cost
measured client latency
finish reason
router attempt number
same-model provider fallback
configured provider preferences
```

Missing optional provider metadata remains `null`; it is not inferred.

The client can build a `crypto-market-generation-provenance/v1` object containing source-snapshot and evidence hashes, prompt and completion hashes, generation parameters, usage, model/provider identity, routing state, generation ID, timestamp and cost.

## Responsibility boundary

The client performs:

```text
configuration validation
bounded provider request
model and routing identity checks
secret-safe error handling
typed provider metadata and provenance construction
```

It does not perform:

```text
claim acceptance
Markdown rendering
branch or pull-request creation
publication
model evaluation approval
scheduling
cross-model fallback
```

For the broader data and authority separation, see [Evidence and analysis boundary](../explanation/evidence-and-analysis-boundary.md).
