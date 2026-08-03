# Phase 7 — Low-cost candidate-selector Stage 0 decision

Status: approved.  
Decision date: 2026-08-03.  
Decision issue: #323  
Parent phase: #314  
Stage 0 contract: #315

## Decision

Do **not** authorise the five-case Stage 1 comparison from the Phase 7 Stage 0 evidence.

No reviewed low-cost model/provider pair demonstrated compatibility with the exact
Stage 0 route, provider-policy and strict-schema boundary. No model is approved,
selected or enabled.

The deterministic Phase 6 selector remains the sole active candidate-selection path.
Automatic report generation, scheduling and publication remain disabled and separately
governed.

## Evidence conclusion

Protected Stage 0 run `30780938812` completed successfully as a governed screen at
trusted commit:

```text
c5e22c35ab23d0ff43b0801e2d1675216d5cbc2b
```

Workflow success means the configured checks completed and retained classifications. It
does not mean a model passed compatibility.

The exact result was:

```text
Candidate count:              201
Compact request bytes:        46,022
Route probes:                 3
Selector generations:         0
Paid-call ledger:             3
Reserved governed cost:       USD 0.020
Compatible models:            0
Semantic repairs:             0
Network retries:              0
Stage 1 authorised by run:    false
```

No selector generation occurred. The evidence therefore contains no candidate-selection
quality, candidate usefulness, latency, token, reconstruction, rendering, stability or
output-validity result for any model.

## Real request identity

Secret-free preparation regenerated the Phase 6 `historical-degraded-sparse` case and
its complete 201-candidate catalogue from trusted repository inputs.

```text
Compact request ID: sha256:7ecd536db61a99a33eea0a90cc667935c381d58ff93684bbc953eb0c4b308ce0
Compact bytes:      46,022
```

The provider-visible request preserved every complete candidate ID in canonical order,
the canonical request identity, bounded editorial fields and the existing selection
limits. The screen did not use a toy prompt, shortlist or post-hoc candidate filtering.

## Model classifications

### DeepSeek V4 Flash 0731

```text
Requested model:   deepseek/deepseek-v4-flash-0731
Approved provider: DeepSeek
Classification:    route-ineligible
Governed cost:     USD 0.005 reserved
Selector calls:    0
```

The model catalogue entry was available, inside the reviewed catalogue-price caps and
advertised both `response_format` and `structured_outputs`. The exact reviewed request
and provider lock nevertheless produced:

```text
No endpoints found that can handle the requested parameters.
```

This is a route-eligibility result for the exact configuration and execution date. It is
not a claim about DeepSeek model quality or about every possible DeepSeek route.

### GPT-OSS 120B

```text
Requested model:   openai/gpt-oss-120b
Approved provider: DeepInfra
Classification:    inconclusive-infrastructure
Governed cost:     USD 0.005 reserved
Selector calls:    0
```

The catalogue entry was available, within price caps and advertised the required
structured-output parameters. The route probe returned without usable
`message.content`. Trustworthy route completion and metering evidence was therefore not
available, and the reviewed route ceiling was reserved.

This is not a GPT-OSS model-quality failure. No real candidate selection was requested
or scored.

### Mercury 2

```text
Requested model:   inception/mercury-2
Approved provider: Inception
Classification:    inconclusive-infrastructure
Governed cost:     USD 0.010 reserved
Selector calls:    0
```

The catalogue entry was available, within price caps and advertised the required
structured-output parameters. The route probe returned without usable
`message.content`. Trustworthy route completion and metering evidence was therefore not
available, and the reviewed route ceiling was reserved.

This is not a Mercury model-quality failure. No real candidate selection was requested
or scored.

## Cost interpretation

The Stage 0 ledger records USD `0.020` because the runner reserved the reviewed maximum
for each failed or incomplete route probe:

```text
DeepSeek route: USD 0.005
GPT-OSS route:  USD 0.005
Mercury route:  USD 0.010
```

This is the governed accounting amount used for fail-closed budget enforcement. It must
not be represented as proof that OpenRouter necessarily charged exactly USD 0.020.

The run remained inside the reviewed USD 0.060 whole-screen ceiling and made no selector
generation, repair or retry call.

## Retained artefacts

Prepared input artefact:

```text
Artifact ID: 8843606111
Digest: sha256:a25004953c6fa46bc40157a7dc1cca482c1d3f8210c376235892c2ec6b7e387e
```

Protected result artefact:

```text
Artifact ID: 8843610508
Digest: sha256:416171e18ea8ef5253dbc7154b7df58f6dbba7fe8f0ca1c7dad0340fcce64c91
```

The protected result retains catalogue checks, route records, reserved metering,
trusted SHA, compact request identity, terminal classifications and the machine-readable
summary. No raw selector completion exists because no selector generation occurred.

## Rationale

Stage 0 existed to prevent a larger five-case evaluation from being authorised merely
because models were inexpensive or advertised structured output at catalogue level.
The required evidence was one exact provider route and one real strict-schema selector
call per model.

None of the three reviewed pairs reached that minimum compatibility proof:

- DeepSeek had no exact eligible route;
- GPT-OSS had incomplete route-probe evidence;
- Mercury had incomplete route-probe evidence;
- no model reached the real 201-candidate selection request;
- no complete model result exists to justify expanded paid evaluation.

The correct governance response is therefore to stop before Stage 1 rather than weaken
provider locks, structured-output requirements, data policy or evidence standards in the
same experiment.

## Operational consequences

- The deterministic Phase 6 selector remains the sole active selector.
- No bounded model selector is enabled for production or research execution.
- Stage 1 is not authorised.
- No second Stage 0 run is authorised.
- The completed nonce must not be reused.
- The temporary paid workflow is archived from the Actions UI.
- Stage 0 configuration, runner, tests, documentation and Git history remain auditable.
- Raw protected evidence remains in the retained Actions artefacts only.
- Automatic report generation, scheduling and publication remain disabled.
- No model alias, provider substitution or relaxed fallback is approved by this decision.

## Future reconsideration

A future investigation may be justified only when it materially changes the evidence
available before paid execution. Examples include independently verified endpoint-level
support for the exact required schema and policy parameters, or a deliberately reviewed
alternative provider-route design.

Any future work requires:

- a new issue and explicit repository-owner authority;
- a current model and endpoint catalogue snapshot;
- one explicitly reviewed provider per model;
- a new route and cost plan;
- a fresh nonce or supported dispatch mechanism;
- a new stop-loss;
- separate authority for any corpus evaluation or operational enablement.

It may not reuse run `30780938812`, its nonce, the archived workflow or the completed
Stage 0 budget. It must preserve the distinction between route/infrastructure evidence
and model quality.

Until such work is approved, Phase 7 is complete with no Stage 1 and deterministic
selection remains final for the active roadmap.
