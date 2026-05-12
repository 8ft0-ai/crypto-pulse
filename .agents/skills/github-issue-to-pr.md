# GitHub issue to PR workflow

Use this skill when the user asks an agent to implement a GitHub issue and open a pull request.

## Goal

Complete the full issue-to-PR path in one coherent run. Do not stop at branch creation, first edit, or another routine checkpoint once implementation has been authorised.

## Workflow

1. Fetch and read the issue body, labels, comments, and linked PR context where relevant.
2. Treat the issue acceptance criteria as the source of truth.
3. Inspect current `main` before editing.
4. Identify every file class required by the issue before writing changes.
5. Decide whether the change should use the `Apply AI Patch` workflow, lower-level Git object writes, or the contents API fallback.
6. Prefer one branch, one coherent implementation commit, and one PR.
7. Implement all required files before opening the PR.
8. Verify the final changed-file list and confirm generated `_site/` output is absent.
9. Open the PR only when it is complete enough to merge.

## Choosing an edit path

Prefer the repository `Apply AI Patch` workflow for multi-file work, especially when generator, CSS, workflow, or runbook files are changed together.

Use contents API updates only when the patch workflow cannot be triggered from the current environment or when the change is a safe, small file edit. If contents updates are used for multi-file work, state that limitation in the PR body.

Do not use full-file contents replacement for large files when fetched content was truncated. Use a patch workflow or split the work first.

## Completion discipline

Handle recoverable SHA conflicts, branch creation conflicts, and connector limitations internally. Refresh the file SHA or branch state and continue.

Stop early only for a hard safety issue, unsafe repository state, truncated large-file content with no safe patch route, or destructive/scope-changing action requiring explicit approval.

Do not open placeholder, CSS-only, or partial PRs unless explicitly requested by the user.

## PR body checklist

Every issue PR should include:

- `Closes #<issue-number>`;
- a summary;
- changed files;
- an acceptance criteria checklist;
- verification notes;
- limitations, especially if the preferred patch workflow could not be used.

## Superseding bad PRs

When an issue exists because an earlier PR failed, inspect the failure mode first. If a bad PR is still open, close or supersede it only when asked or when the issue explicitly requires that action. The replacement PR must address the root process failure, not merely repeat the visible code changes.
