# Deliver a repository slice

> **Mode:** How-to  
> **Audience:** CryptoPulse contributors and coding agents  
> **Outcome:** Deliver one bounded issue through a branch, pull request, validation gate and evidence-backed merge.

## 1. Revalidate the issue

Read the issue, its parent initiative or phase record, dependencies and current `main`. Confirm that the acceptance criteria still describe the required outcome and that the issue is unblocked.

Do not close the issue when a branch is created. The issue remains open until its pull request merges or the work is explicitly abandoned or superseded.

## 2. Create a fresh branch

Create a short, descriptive branch from current `main`:

```bash
git switch main
git pull --ff-only
git switch -c <branch-name>
```

Use one branch for one execution issue. Avoid unrelated cleanup.

## 3. Implement the complete bounded change

Make the smallest coherent change set that satisfies the issue. For multi-file agent work, follow [Choose an agent write strategy](choose-agent-write-strategy.md).

Do not edit generated `_site/` content as source. Do not broaden documentation or process work into product behaviour unless the issue explicitly requires it.

## 4. Review the changed scope

Inspect the complete diff and changed-file list:

```bash
git status --short
git diff --check
git diff --stat
git diff
```

Confirm that every changed path belongs to the issue and no generated or secret-bearing artefact is present.

## 5. Run validation

Run the smallest focused checks first, then the repository baseline:

```bash
python -m unittest discover -s tests
python -m site_generator
```

For site-affecting work, inspect the expected `_site/` paths locally. For documentation moves, check every incoming relative link and old path.

Confirm generated output is not staged:

```bash
git diff --cached --name-only -- _site
git ls-files _site
```

Both commands must produce no output.

## 6. Commit and push

Create an imperative commit and push the branch:

```bash
git add <expected-paths>
git commit -m "<imperative summary>"
git push --set-upstream origin <branch-name>
```

Before committing, inspect the staged file list rather than using an unrestricted `git add .` for a sensitive or generated-output change.

## 7. Open the pull request

Target `main` and include:

```markdown
## Summary

Closes #<issue>.

## Outcome

## Changes

## Validation

## Scope boundaries

## Notes / limitations
```

Record exact commands, workflow runs, changed paths and known limitations. For a documentation migration, include old-to-new path mappings. For a generated report, include every field required by [Generated report PR evidence](../reference/generated-report-pr-evidence.md).

## 8. Pass the merge gate

Wait for required checks and review. If a check fails:

1. identify the exact failure;
2. correct branch-introduced problems on the same pull request;
3. run focused validation;
4. rerun the full required checks;
5. avoid repeated undiagnosed reruns.

Resolve review threads only after the requested change or evidence is present.

Use the repository's preferred squash merge after the pull request is mergeable and all required evidence is complete. Do not bypass protection, disable checks or merge a failing branch.

## 9. Verify and close

After merge:

1. confirm the change exists on `main`;
2. confirm the execution issue closed;
3. record the pull request, merge commit and validation evidence on the parent issue or planning record;
4. begin the next dependent issue only from refreshed `main`.

For branch-protection configuration, see [Configure main branch protection](configure-main-branch-protection.md).
