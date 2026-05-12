# Large-file safe editing

Use this skill before editing large source files, generated-site renderers, large CSS/JS assets, or complex workflow YAML files.

## Hard rule

Never full-replace a large file from truncated content. If the current file was not fetched completely, do not reconstruct, infer, or guess omitted sections.

This rule applies especially to:

- `scripts/build_pages_site.py`;
- generated-site renderers;
- large CSS or JavaScript assets;
- complex GitHub Actions workflow YAML files.

## Preferred strategy

For `scripts/build_pages_site.py` and other large implementation files, prefer the repository `Apply AI Patch` workflow. A narrow patch should preserve unmodified sections exactly and only touch the required lines.

If workflow dispatch is not available, use the safest available fallback only when the full current file content has been fetched without truncation.

## Safe editing practices

- Preserve unmodified sections exactly.
- Keep changes narrow and reviewable.
- Avoid opportunistic formatting cleanup.
- Do not rewrite file tails, helper functions, imports, or comments that are unrelated to the issue.
- Do not combine a large-file edit with unrelated cleanup.

## When a file is too large to edit safely

If the file cannot be safely patched and the required content is truncated, stop before writing the file. Recommend one of these paths:

1. run the `Apply AI Patch` workflow with a narrow patch;
2. prepare a manual patch for workflow dispatch;
3. create a smaller refactor issue to split the file into safer modules first.

Do not open a PR with incomplete large-file changes. Do not create a placeholder PR that claims the issue is in progress but omits the required generator or renderer changes.

## Verification

Before opening a PR, compare the branch against `main` and confirm:

- only intended large files changed;
- no generated `_site/` files changed;
- the diff is narrow;
- no unseen or truncated content was reconstructed;
- the PR body states any limitation in the edit method.
