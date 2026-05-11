# Slice delivery process

CryptoPulse implementation slices should be delivered through pull requests, not direct commits to `main`.

This keeps changes reviewable, preserves a clear history, and avoids confusion between issues, pull requests, and direct commits.

## Standard workflow

1. Select the next open slice issue.
2. Create a branch from the latest `main`.
3. Name the branch clearly, for example:

   ```text
   slice-06-latest-market-read
   slice-07-report-card-metadata
   fix-mobile-report-tables
   ```

4. Commit implementation work to that branch only.
5. Open a pull request targeting `main`.
6. Link the PR to the issue using `Closes #<issue-number>` or `Refs #<issue-number>`.
7. Include verification evidence in the PR body.
8. Wait for checks and review before merge.
9. Merge the PR.
10. Close the issue through the PR or after the PR has merged.

## Direct commits to `main`

Direct commits to `main` should be avoided for implementation slices.

Direct commits are acceptable only for:

- archiving generated report Markdown when explicitly requested;
- urgent break/fix changes where the user explicitly approves direct commit;
- repository administration changes where a PR would add no value and the user explicitly approves direct commit.

If direct commit is used, the final response must say so clearly and include the commit SHA.

## Issue handling

Issues should remain open while work is in progress.

Do not close an issue merely because a branch has been created. Close it only when:

- the linked PR has been merged; or
- the user explicitly decides not to proceed; or
- the issue is superseded by another issue.

## Pull request expectations

Each slice PR should include:

- linked issue;
- scope of change;
- files changed;
- verification performed;
- screenshots or local preview notes where relevant;
- known limitations;
- rollback notes if useful.

## Verification expectations

For site-generator changes, run or document the expected local commands:

```bash
python scripts/build_pages_site.py
python -m http.server 8000 --directory _site
```

If the project uses an alternate wrapper, use the configured workflow command instead.

For GitHub Pages deployment changes, check the workflow status when connector access allows it. If workflow metadata is unavailable, state that clearly rather than implying success.

## ChatGPT implementation rule

When ChatGPT is asked to implement the next slice:

1. It should create or reuse a branch.
2. It should commit to that branch, not `main`.
3. It should open a pull request.
4. It should leave the issue open until the PR is merged.
5. It should report the PR URL and branch name in the final response.

This process is mandatory unless the user explicitly asks for a direct commit to `main`.
