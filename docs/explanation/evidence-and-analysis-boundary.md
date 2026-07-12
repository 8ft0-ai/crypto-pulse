# Evidence and analysis boundary

> **Mode:** Explanation  
> **Audience:** CryptoPulse architects, reviewers and governance stakeholders  
> **Outcome:** Understand why optional LLM analysis is separated from market evidence, deterministic rendering and publication authority.

CryptoPulse treats a validated source snapshot as evidence and an LLM response as a candidate interpretation of that evidence. Those are deliberately different trust classes.

The distinction prevents a fluent model response from silently becoming a market-data source, a document template or a publication decision. The model may propose a bounded structured analysis, but repository code decides whether every claim is supportable and owns every artefact that can be reviewed or published.

## Evidence comes before analysis

The system begins with an immutable checked-in source snapshot. Existing repository validators decide whether that snapshot is usable, degraded or invalid before any model is involved.

Repository code then projects the accepted snapshot into a smaller evidence bundle. This projection is important for two reasons.

First, it limits the model to facts and quality signals that have already crossed the source-validation boundary. The model cannot choose a new market-data source, browse for context or add a fact that happens to sound plausible.

Second, it gives each permissible fact a stable evidence identifier. A generated claim must point back to those identifiers, allowing repository code to test whether names, numbers, timestamps, units, directions and comparisons remain anchored to the original evidence.

## The model selects claims, not facts

The model's useful role is narrow but meaningful. It can select, organise and relate supported observations into a concise structured response. It may identify which validated facts are worth presenting together or express a restrained interpretation when the contract permits it.

It cannot:

- create or fetch evidence;
- infer unsupported causes;
- predict future prices or direction;
- create targets, signals or portfolio actions;
- rewrite the project's product and non-advice boundaries;
- decide that an invalid or degraded source is acceptable;
- control Markdown structure;
- merge or publish its own output.

This is why the provider returns JSON rather than a finished report. Structured output makes the proposed claims inspectable before they receive document form.

## Deterministic code owns acceptance

A schema-valid object can still be wrong. It may cite a real evidence identifier while misstating the value, compare incompatible measurements, attach the wrong source name, introduce a forecast or repeat an instruction embedded in untrusted source text.

CryptoPulse therefore treats schema validation as only the first gate. Referential, value, semantic and policy checks must also pass. When deterministic code cannot prove that a claim is inside the contract, the claim is rejected rather than treated as probably safe.

The exact checks are described in [Offline validation pipeline](../reference/offline-validation-pipeline.md). The rationale for rejecting uncertain outputs is expanded in [Fail-closed analysis validation](fail-closed-analysis-validation.md).

## Repository code owns prose structure

Even accepted model text is not allowed to control the document.

The deterministic renderer owns:

- headings and section order;
- fixed disclaimers and product boundaries;
- metadata and evidence annotations;
- the display of claim type and confidence;
- schema and prompt version references;
- Markdown escaping and whitespace normalisation.

This boundary prevents a model-controlled string from creating links, headings, HTML or other document structure. It also means identical accepted structured inputs produce identical Markdown bytes.

The LLM can contribute analysis while the repository remains the author of the published artefact.

## Provenance binds the layers

An accepted result is useful only if a reviewer can reconstruct how it was produced. Provenance binds together:

```text
source snapshot
validated evidence bundle
prompt and schemas
requested and actual model/provider
generation parameters and routing
raw completion hash
accepted structured analysis
deterministic report
trusted repository commit
validation outcome
```

This chain separates evidence of what the market-data sources recorded from evidence of what the model proposed and evidence of what repository code accepted.

Previous generated analysis is never promoted into the next evidence bundle. Without that rule, model interpretation could gradually become self-referential evidence.

## Publication remains a separate authority

Acceptance does not equal publication.

The artefact-only dry run stops after producing review evidence. The rolling-review workflow may create three controlled source files only after reproducing the accepted result, checking exact scope, running all tests and building the site. It opens or updates a normal pull request; it does not merge it.

This creates four distinct authorities:

```text
source validators decide whether evidence is usable
model proposes structured claims
repository validators and renderer decide whether output is acceptable
normal repository review decides whether accepted source files are merged
```

No single model call crosses all four boundaries.

## Why the deterministic report still matters

The governed analysis path is optional. Deterministic report generation remains useful without a provider secret and must not be blocked by model unavailability, routing failure or rejected analysis.

This gives CryptoPulse a safe fallback that is more than an error page: validated source evidence can still be archived and rendered even when the optional analysis layer cannot contribute.

The model is therefore an enhancement over an evidence spine, not the foundation of that spine.

## The practical consequence

When reviewing a governed result, the central question is not whether the prose sounds convincing. It is whether the complete chain proves:

1. the source snapshot was valid;
2. the evidence bundle contains only permitted source facts and boundaries;
3. every proposed claim is traceable and contract-compliant;
4. the rendered report is reproducible from accepted structured data;
5. the repository change is scoped, reviewed and independently validated.

The canonical contract for those obligations is [Governed analysis contract](../reference/governed-analysis-contract.md).
