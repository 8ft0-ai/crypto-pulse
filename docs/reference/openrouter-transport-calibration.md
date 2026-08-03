# Observable OpenRouter transport calibration

> **Mode:** Reference  
> **Audience:** CryptoPulse developers, reviewers and governance stakeholders  
> **Status:** Phase 8 execution contract under issue #325

## Decision question

> Can at least one model complete the real candidate-ID request under an observable, realistically configured route?

Phase 8 tests transport operability only. It does not reopen the Phase 6 quality decision, approve a model selector, change deterministic ranking, generate a report or publish the site.

## Why Phase 8 exists

The Phase 7 route probe allowed only 16 output tokens and required final `message.content` before retaining the complete response. Reasoning-capable models could therefore be rejected without preserving whether the response contained reasoning, a length finish, usage, cost or router metadata.

Phase 8 removes that generated toy probe. The first paid request is the real compact 201-candidate selector request.

## Fixed candidates

```text
1. inception/mercury-2
2. openai/gpt-oss-120b
```

Mercury is attempted first. GPT-OSS is attempted only when Mercury discovery does not complete.

## Stage A — discovery

The router receives the complete compact request with:

```text
strict JSON Schema
require_parameters: true
data_collection: deny
provider pin: none
preferred provider order: configured
provider fallback: allowed
reasoning effort: minimal
reasoning returned: excluded
max output tokens: 2,048
```

The HTTP status, allowlisted response headers, raw body hash and protected raw body are written before JSON parsing or any metering, identity or content judgment.

A discovery is complete only when model identity, router-selected provider, usage, cost, candidate envelope, repository validation, canonical reconstruction and deterministic rendering all pass.

## Stage B — reproduction

The observed provider name is mapped to a reviewed canonical provider slug. The same real request is repeated once with:

```text
provider.only: [observed canonical slug]
allow_fallbacks: false
```

Reproduction proves that the observable route can be pinned and used again. It does not require identical selected IDs and does not establish quality or stability.

## Budget

```text
maximum discovery calls:     2
maximum reproduction calls:  1
maximum paid calls:          3
maximum per-call cost:       USD 0.025
maximum total cost:          USD 0.060
semantic repairs:            0
network retries:             0
```

A network-started call without trustworthy metering reserves the full USD 0.025 call ceiling.

## Retained evidence

For every response, including failures, the protected artifact retains:

- request hash and byte count;
- HTTP status and allowlisted headers;
- raw response hash and protected body;
- requested and actual model;
- router metadata, provider and attempts;
- content presence, finish reason, reasoning and reasoning details;
- usage and cost;
- candidate validation diagnostics;
- reconstructed plan and rendered-output hashes when accepted.

No provider output writes repository state. Raw output is never committed or published.

## Permanent boundaries

The deterministic Phase 6 selector remains the sole active selector. Automatic generation, scheduling and publication remain disabled. The temporary paid workflow must be archived after the one authorised run, and a separate decision must record the result.