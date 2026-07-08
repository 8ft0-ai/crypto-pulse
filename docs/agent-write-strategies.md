# Agent write strategies

This repository prefers an issue-to-branch-to-PR workflow for agent changes. The write mechanism used to create the branch matters, but it is secondary to the review boundary: scoped issue, isolated branch, reviewable diff, validation, and no committed `_site/` output.

## Default preference

Use the repository `Apply AI Patch` workflow when it is available and appropriate.

That workflow is preferred because it supports:

- one feature branch;
- one coherent implementation commit;
- one pull request;
- automatic rejection of generated `_site/` output;
- a clear PR body with summary and verification notes.

This preference is not a hard requirement in every agent environment. Some connector sessions cannot dispatch GitHub Actions workflows, some changes are small enough that the contents API is safer and simpler, and some large-file changes require a different safe editing path.

## Write-path hierarchy

Use this hierarchy when choosing how to write repository changes.

### Tier 1 — `Apply AI Patch` workflow

Preferred for multi-file implementation work when workflow dispatch is available.

Use it when:

- the change spans multiple files;
- generator, CSS, workflow, runbook, or documentation files are changed together;
- one atomic implementation commit would make the PR easier to review;
- the patch can be prepared safely and does not include generated `_site/` output.

### Tier 2 — Lower-level Git object or atomic commit path

Acceptable when available and safe.

Use it when:

- the environment can create blobs, trees, commits, and branch refs directly;
- one coherent commit can be produced without relying on full-file replacement of large files;
- the branch can still be opened as a normal PR against `main`.

This is a good fallback when `Apply AI Patch` cannot be dispatched but atomic review shape can still be preserved.

### Tier 3 — GitHub contents API fallback

Acceptable for small, low-risk changes, especially when files are new or have been safely fetched in full.

Use it when:

- the patch workflow cannot be triggered from the current environment;
- the change is small, new, or documentation-only;
- the file being updated has been fetched fully and was not truncated;
- the resulting PR remains easy to review even if multiple small commits are produced.

When this fallback is used for multi-file work, disclose it in the PR body.

### Tier 4 — Stop or hand off

Stop before writing when the required edit cannot be made safely.

Stop or hand off when:

- the change requires replacing a large file and the file fetch was truncated;
- the patch workflow is unavailable and no lower-level atomic commit path is available;
- the change would touch generated `_site/` output;
- the task requires destructive or scope-changing action not covered by the issue;
- repository state is ambiguous or unsafe.

Do not open a placeholder PR just to reserve a branch.

## PR disclosure for fallback paths

When an agent does not use `Apply AI Patch` for multi-file work, the PR body should include a `Notes / limitations` section that states:

- why `Apply AI Patch` was not used;
- which write path was used instead;
- whether the fallback produced multiple commits;
- how changed files were verified;
- confirmation that no generated `_site/` output was committed.

Example:

```markdown
## Notes / limitations

- The preferred `Apply AI Patch` workflow could not be dispatched from this connector session, so this implementation used the GitHub contents API fallback.
- The fallback produced two small file-level commits instead of one atomic implementation commit.
- The changed files were fetched and verified before opening the PR.
- No generated `_site/` output was committed.
```

## Non-negotiable boundaries

Regardless of write path, agent changes must preserve these repository rules:

- Work from an issue unless the user explicitly requests otherwise.
- Create a branch and open a PR against `main`.
- Keep the change scoped to the issue.
- Do not commit generated `_site/` output.
- Do not use full-file contents replacement for large or truncated files.
- Do not broaden a task from documentation/process clarification into workflow behaviour change unless the issue says so.
- Include verification notes and known limitations in the PR body.

## Practical interpretation

A fallback write path is not automatically a process failure. It becomes a process failure when the fallback is unsafe, undisclosed, too broad, or produces a PR that is hard to review.

The control surface is the issue and PR. The write mechanism should support that control surface, not replace it.
