# Fail-closed analysis validation

> **Mode:** Explanation  
> **Audience:** CryptoPulse architects, developers and governance reviewers  
> **Outcome:** Understand why uncertain or partially valid model output is rejected rather than repaired, published or treated as a degraded success.

A language model can return valid JSON that is still unsafe or unsupported. It may cite a real evidence identifier while changing the sign of a value, use a compatible-sounding but wrong unit, compare observations from different periods or phrase an interpretation as a forecast.

CryptoPulse therefore fails closed. A result is accepted only when deterministic checks can establish every required property. Uncertainty is not converted into approval.

## Validation is a chain, not one score

The acceptance pipeline is intentionally layered:

```text
schema
references
values
semantics
policy
rendering
```

Each layer answers a different question.

Schema validation asks whether the object has the permitted shape. Referential validation asks whether cited evidence exists. Value validation asks whether stated numbers, units, timestamps and entities match that evidence. Semantic validation asks whether the evidence can support the declared kind of claim. Policy validation asks whether the output introduces prohibited advice, forecasting, causality or instruction overrides. Rendering then proves that repository code can reproduce the final document safely.

A result that passes five of six layers is not mostly accepted. The missing property is precisely the boundary the system cannot prove.

## Why the pipeline does not silently repair output

Automatic repair would create a new authority problem. If repository code rewrote an unsupported claim into something that appears acceptable, it would become difficult to distinguish:

- what the model proposed;
- what deterministic code corrected;
- what a reviewer actually approved.

Repair can also hide systematic model behaviour. A repeated sign error, evidence mismatch or taxonomy problem should remain visible in diagnostics and evaluation evidence rather than disappear behind a successful-looking report.

The pipeline may canonicalise accepted data and escape text for safe rendering. It does not reinterpret a rejected claim into a different claim.

## Diagnostic evidence is retained without promoting output

Failing closed does not mean discarding all information about the run.

Where execution reaches the orchestration layer, the workflow retains a validation report, status record, generation metadata and summary. These artefacts let reviewers identify whether the failure came from routing, transport, schema, evidence references, values, semantics or policy.

At the same time, the workflow removes or refuses to create the files that signal acceptance. A rejected run must not leave an older `accepted-analysis.json` or rendered preview in place, because stale output could be mistaken for the current result.

This distinction supports investigation without creating an ambiguous publication artefact.

## Prompt injection is treated as data contamination, not instruction

Source snapshots may contain strings that resemble commands. The evidence bundle preserves them as untrusted data, and the prompt explicitly separates that data from trusted repository instructions.

If generated analysis repeats or obeys an override instruction, policy validation rejects it. The system does not try to determine whether the instruction was malicious, accidental or harmless. The relevant fact is that source data attempted to influence behaviour outside its role.

The deterministic renderer provides a second boundary by escaping Markdown controls and owning the document structure.

## Provider failure and analytical rejection are both bounded outcomes

Fail-closed behaviour applies before and after the model call.

Before generation, invalid paths, invalid snapshots, missing secrets, ineligible routes and configuration errors stop the workflow. During transport, bounded retry and cost controls prevent an uncontrolled attempt loop. After generation, malformed responses and unsupported claims prevent acceptance.

These failures have different diagnostic categories, but they share one consequence: no accepted source file crosses the boundary.

## Optional analysis must not block deterministic evidence

The deterministic source and report path remains independent from governed LLM analysis. This matters because model availability, provider routing and stochastic output are inherently less predictable than repository-owned validation and rendering.

When the optional analysis path fails, CryptoPulse can retain the validated source snapshot and deterministic report. It does not need to weaken controls or invent a substitute model response to keep the core archive functioning.

## Why no-op is also a valid result

The rolling workflow can accept an analysis and still make no repository change when the intended source files are identical to the current rolling branch or `main`.

Creating an empty commit would falsely suggest that new evidence or analysis had landed. The workflow therefore treats exact no-op detection as part of its proof boundary.

## Review principle

A reviewer should read a failed run as evidence that a control worked, not automatically as a defect in the control.

The appropriate next step depends on the diagnosed cause:

- correct malformed or invalid source evidence;
- revise configuration through review;
- investigate provider reliability;
- improve a versioned prompt or schema through a new contract version where required;
- reject a model or profile that cannot satisfy the current contract;
- preserve the deterministic-only path.

The inappropriate response is to disable a check, relax privacy or routing policy, or manually copy rejected output into a report merely to obtain a successful-looking result.

For the exact checks and exit behaviour, see [Offline validation pipeline](../reference/offline-validation-pipeline.md). For the provider-side bounds, see [Governed OpenRouter client](../reference/governed-openrouter-client.md).
