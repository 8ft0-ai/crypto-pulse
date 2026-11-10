# Choose an agent write strategy

> **Mode:** How-to  
> **Audience:** Coding agents and maintainers  
> **Outcome:** Select the safest available repository write mechanism while preserving the issue, branch, review and validation boundaries.

The write mechanism is secondary to the delivery contract. Every strategy must produce a scoped branch, reviewable pull request, complete validation evidence and no committed `_site/` output.

## Use the preferred hierarchy

### 1. Apply AI Patch workflow

Use [`.github/workflows/apply-ai-patch.yml`](../../.github/workflows/apply-ai-patch.yml) for multi-file work when workflow dispatch is available.

It is the preferred path when:

- several related files must change together;
- one atomic implementation commit improves reviewability;
- the patch can be generated from a real working tree;
- `git apply --check` succeeds;
- the patch contains no generated `_site/` content.

Generate the patch from an exact checkout rather than composing diff hunks manually:

```bash
git diff --binary > patch.diff
git apply --check patch.diff
```

### 2. Lower-level atomic Git write

Use a blob/tree/commit/ref path when the environment supports it safely. Prepare every changed file first, create one coherent commit from current `main`, update the feature branch once and open a normal pull request.

### 3. GitHub contents API

Use per-file contents operations only when the preferred workflow and atomic Git path are unavailable and the change remains safe to review.

This is suitable when:

- files are new or small;
- every existing file was fetched in full;
- no large or truncated source file must be reconstructed;
- multiple small commits do not obscure the pull-request outcome.

For multi-file work, disclose the fallback in the pull-request body, including why it was used, how many commits it produced, how the changed-file scope was checked and that `_site/` was not committed.

### 4. Stop the unsafe branch of work

Do not write when:

- an existing large file was returned only in truncated form;
- no patch or safe atomic edit path exists;
- repository state is ambiguous;
- the task requires destructive or scope-changing action outside the issue;
- the proposed change would edit generated `_site/` output.

Do not open a placeholder pull request merely to reserve a branch.

## Preserve the delivery boundary

Regardless of write mechanism:

1. start from the current `main` commit;
2. work from an issue or explicit user request;
3. keep one bounded implementation outcome per pull request;
4. run focused and repository-wide validation;
5. inspect the full changed-file list;
6. confirm `_site/` is neither tracked nor staged;
7. record evidence and limitations in the pull-request body;
8. merge only after required checks and review policy pass.

For the complete issue-to-merge procedure, see [Deliver a repository slice](deliver-a-repository-slice.md). Machine-oriented constraints remain authoritative in [`AGENTS.md`](../../AGENTS.md) and [`.agents/skills/`](../../.agents/skills/).
