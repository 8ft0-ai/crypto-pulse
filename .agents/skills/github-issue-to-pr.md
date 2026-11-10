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

`Apply AI Patch` is the preferred write path for multi-file agent changes because it gives the repository one branch, one coherent implementation commit, and one pull request. It is not a hard requirement in every execution environment.

Use this hierarchy:

1. Prefer the repository `Apply AI Patch` workflow for multi-file changes when workflow dispatch is available, especially when generator, CSS, workflow, or runbook files are changed together.
2. Use a lower-level Git object or atomic commit path when available and safe, especially when it can preserve the one-commit review shape without full-file replacement risk.
3. Use the GitHub contents API fallback when the patch workflow cannot be triggered from the current environment, or when the change is limited to small, new, or safely fetched files.
4. Stop or hand off when the required change touches large or truncated files and no safe patch or atomic commit path is available.

Do not use full-file contents replacement for large files when fetched content was truncated. Use a patch workflow, a lower-level atomic commit path, or split the work first.

When contents API updates are used for multi-file work, state that limitation in the PR body. Include why `Apply AI Patch` was not used, which fallback write path was used, whether multiple commits were produced, how the changed files were verified, and confirmation that generated `_site/` output was not committed.

For more detail, see `docs/agent-write-strategies.md`.

## Completion discipline

Handle recoverable SHA conflicts, branch creation conflicts, and connector limitations internally. Refresh the file SHA or branch state and continue.

Stop early only for a hard safety issue, unsafe repository state, truncated large-file content with no safe patch route, or destructive/scope-changing action requiring explicit user approval.

Do not open placeholder, CSS-only, or partial PRs unless explicitly requested by the user.

## Planning close-out discipline

`planning/` is the repository planning control surface. It is separate from `docs/`, which is for repository, product, and engineering documentation.

Small non-phase PRs do not need to update planning records unless they materially change the roadmap, delivery history, or planning model.

A PR that closes a delivery phase must update, or explicitly mark as not applicable, these planning assets:

```text
planning/delivery/<phase>.md
planning/delivery-log.md
planning/delivery/delivery.yaml
planning/delivery/graph.md
```

The delivery graph is generated output from the YAML metadata. When `planning/delivery/delivery.yaml` changes, regenerate and commit the graph:

```bash
python scripts/render_delivery_graph.py
python scripts/validate_delivery_graph.py
```

Update roadmap files only when planning intent changes. Examples include new phase direction, changed phase scope, changed acceptance gates, or a new future roadmap spec:

```text
planning/roadmap/index.md
planning/roadmap/<phase-or-next-phase>.md
```

Do not move raw report truth into planning records. Raw Markdown reports remain the source of truth, and generated `_site/` output remains disposable and must not be committed.

## PR body checklist

Every issue PR should include:

- `Closes #<issue-number>`;
- a summary;
- changed files;
- an acceptance criteria checklist;
- verification notes;
- limitations, especially if the preferred patch workflow could not be used.

For phase close-out PRs, also include evidence that the relevant planning delivery record, delivery log, delivery YAML, and generated graph were updated or explicitly marked not applicable.

## Superseding bad PRs

When an issue exists because an earlier PR failed, inspect the failure mode first. If a bad PR is still open, close or supersede it only when asked or when the issue explicitly requires that action. The replacement PR must address the root process failure, not merely repeat the visible code changes.
