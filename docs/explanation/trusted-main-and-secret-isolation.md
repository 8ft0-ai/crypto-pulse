# Trusted main and secret isolation

> **Mode:** Explanation  
> **Audience:** CryptoPulse architects, workflow maintainers and security reviewers  
> **Outcome:** Understand why provider access and repository write authority are separated across trusted workflow jobs.

A workflow that can both execute unreviewed code and receive a provider secret would create an obvious exfiltration path. A workflow that can receive the provider secret and write directly to the repository would also concentrate generation, acceptance and publication authority in one place.

CryptoPulse avoids both patterns by running governed analysis only from a recorded `main` commit and by separating secret-bearing generation from repository-bearing publication.

## Why trusted `main` is the code boundary

Pull requests are where untrusted or not-yet-approved repository changes are reviewed. Giving pull-request code access to `OPENROUTER_API_KEY` would allow the same change being reviewed to alter how the secret is used, logged or transmitted.

The governed workflows therefore accept manual dispatch only and reject a workflow ref other than `main`. A secret-free preparation job checks out current `main`, records its exact commit SHA and creates the evidence bundle. The protected generation job then checks out that exact SHA rather than whatever the branch points to later.

This establishes a concrete statement:

> The provider call executed code that had already landed on `main`, at the recorded commit used to prepare the evidence.

Recording the SHA also protects against branch movement between preparation and generation.

## Why preparation has no secret

The preparation job performs work that should be safe and reproducible without provider access:

- validate the input path;
- validate the selected source snapshot;
- project the deterministic evidence bundle;
- record hashes and the trusted commit;
- upload prepared evidence.

Keeping this job secret-free means malformed input and source-quality failures are rejected before a credential is exposed to any process.

It also makes the evidence projection independently reviewable. The generation job can rebuild the bundle and require byte-equivalent canonical content before calling the provider.

## Why generation has no repository write authority

The protected generation job is the only place where `OPENROUTER_API_KEY` is injected. The secret is scoped to the command that needs it rather than checkout, dependency installation, artefact upload or summary generation.

The job checks out without persisted GitHub credentials and runs with read-only repository permission. It can create workflow artefacts, but it cannot push a branch, open a pull request or deploy a site.

This means a provider response, even an accepted one, cannot write itself into the repository from the secret-bearing context.

## Why publication has no provider secret

The rolling-review workflow introduces a separate prove-and-publish job after generation succeeds. That job has the repository permissions needed to update the controlled branch and pull request, but it does not receive `OPENROUTER_API_KEY`.

It consumes only scrubbed accepted artefacts, reproduces the expected source files using trusted repository code and proves exact scope, tests and static-site generation before pushing.

The split makes the authority flow one-way:

```text
secret-free trusted preparation
        ↓
secret-bearing read-only generation
        ↓
scrubbed accepted artefact
        ↓
secret-free write-capable proof and publication
```

No job simultaneously holds provider credentials and repository write authority.

## Why a protected environment is used

The generation job is attached to the `governed-llm-dry-run` GitHub environment. The environment should be configured for selected branches with `main` as the permitted deployment branch, and the API key should exist only as an environment secret.

A repository-wide or organisation-wide secret available to arbitrary workflows would weaken this boundary. Environment protection can also require human reviewers where governance needs an additional approval point before a provider call.

The environment is not a substitute for the trusted-SHA checks. It is an additional control over when and where the secret becomes available.

## Why checkout credentials differ between jobs

Preparation and generation use:

```yaml
persist-credentials: false
```

They need repository content, not push authority.

The prove-and-publish job checks out with credentials because it must update the controlled branch after proof. That job is deliberately isolated from the provider secret and stages only manifest-declared source paths.

Permissions therefore follow the smallest responsibility of each job rather than the broadest responsibility of the overall workflow.

## What this boundary does not prove

Trusted execution does not prove that:

- the provider will return a useful result;
- the configured model is approved or currently routable;
- the structured analysis is valid;
- the report should be merged;
- the provider has returned every optional metadata field.

Those questions belong to configuration governance, offline validation, evaluation evidence and normal pull-request review.

Secret isolation protects execution authority. It does not replace analytical acceptance.

## Operational consequence

A reviewer approving the protected environment should confirm the code and input boundary, not assess the eventual prose in advance. A reviewer assessing a rolling PR should inspect the accepted analysis, provenance, deterministic report and proof evidence, not assume that environment approval authorised publication.

These are separate review decisions by design.

For exact workflow permissions and job behaviour, see [Governed LLM workflows](../reference/governed-llm-workflows.md). For the provider's own secret and routing controls, see [Governed OpenRouter client](../reference/governed-openrouter-client.md).
