# AGENTS.md

Guidance for AI coding agents working in this repository.

## Repository purpose

CryptoPulse is an AI-generated crypto market report demo and archive.

The repository stores raw generated report examples as Markdown and publishes them as a static GitHub Pages site. Reports are demonstration content only. They may contain errors, stale information, hallucinations, or unsupported claims and must not be treated as financial advice, investment research, recommendations, or trading signals.

## Core product rule

The user should understand that CryptoPulse is AI-generated demo content before they read any market claim.

Any change to the Pages site, README, feed, manifest, or generated report presentation must preserve this positioning.

## Preferred working workflow

Use an issue-to-branch-to-PR workflow.

1. Read the issue or user request.
2. Inspect the repository before editing.
3. Create a short, descriptive branch from the current `main` head.
4. Make the smallest coherent change set.
5. Commit the full change set to the branch.
6. Open a pull request against `main`.
7. Include a clear PR body with summary, files changed, and verification notes.

Avoid asking the user to manually apply patch files unless direct GitHub writes are unavailable.

## Preferred GitHub write strategy

For multi-file implementation work, prefer one atomic Git commit rather than one commit per file.

Where available, prefer the repository workflow:

```text
.github/workflows/apply-ai-patch.yml
```

This workflow exists specifically to support:

- one branch;
- one implementation commit;
- one PR;
- one review/merge decision.

The workflow accepts:

- branch name;
- commit message;
- PR title;
- PR body;
- base64-encoded unified git patch.

Preferred sequence:

1. Prepare all changes locally or in-memory.
2. Generate a unified git patch.
3. Base64 encode the patch.
4. Run `Apply AI Patch` from the GitHub Actions tab.
5. Provide workflow inputs.
6. Allow the workflow to:
   - create/reset the feature branch;
   - apply the patch;
   - reject `_site/` modifications;
   - create one commit;
   - push the branch;
   - open or update the PR.

Only fall back to per-file `update_file` operations when:

1. the patch workflow is unavailable;
2. the environment cannot trigger workflows; or
3. the change is a simple single-file edit.

If forced to use per-file updates for multi-file work, state that explicitly in the PR body under:

```text
Notes / limitations
```

## Hard rules for large or multi-file changes

Large and multi-file changes are high-risk in this repository because they can affect generated site output, report rendering, deployment workflows, or broad CSS reviewability.

Do not use full-file `update_file` replacement for a large source file unless the full current file has been fetched without truncation and the replacement is based on that exact full content.

Large files include:

- `scripts/build_pages_site.py`;
- generated-site renderers;
- large CSS or JavaScript assets;
- complex workflow YAML files.

If a file fetch is truncated, stop using the GitHub contents API for that file. Do not guess, summarise, patch around, or reconstruct omitted file content. Never rebuild an unseen file tail from memory or inference.

When a large file is required and contents output is truncated, use one of these paths instead:

1. the `Apply AI Patch` workflow;
2. a narrow patch prepared for manual workflow dispatch;
3. a smaller refactor issue that first splits the file into safer modules.

If none of those paths is available, stop before writing the large file and explain the safe blocker. Do not open a partial PR to reserve the branch.

For multi-file implementation work, identify all required files before writing, and do not open a PR until all required files for the issue have been updated. A UX issue that requires generator output and CSS must not be opened with CSS-only changes. Generator, markup, metadata, and stylesheet responsibilities must be handled together where the issue requires them.

## Completion discipline for issue-to-PR work

Once the user authorises implementation, complete the issue-to-PR path without stopping at routine checkpoints.

Do not pause after:

- fetching files;
- creating a branch;
- making the first file change;
- hitting a recoverable SHA conflict;
- discovering a routine connector limitation.

Handle routine interruptions internally and continue. Refresh file SHAs, refetch current branch state, use the safe fallback path, and keep going until the branch and PR are complete.

Only stop early for:

- a hard safety issue;
- unsafe repository state;
- truncated source file where no safe patch workflow is available;
- destructive or scope-changing action requiring explicit user approval.

Do not open placeholder PRs, draft-only scaffolding PRs, or incomplete implementation PRs unless the user explicitly asks for a partial PR.

## CSS change discipline

Keep stylesheet changes narrow and reviewable.

Do not reformat, collapse, reorder, or compress large sections of CSS when adding or adjusting a component. Do not convert existing multi-line CSS blocks into one-line blocks. Broad CSS churn creates unnecessary conflicts and makes reviews harder.

Add component-specific CSS near related sections or under a clear label. Check mobile and print media sections when the component affects responsive or printable output. Avoid changing global selectors, resets, typography, spacing variables, or colour systems unless the issue specifically requires it.

Preserve the existing visual system. CSS should complement generator and markup changes, not substitute for missing generator work.

## PR #36 failure mode to avoid

PR #36 is the explicit example of what not to repeat.

Avoid these failure modes:

- CSS-only implementation when generator changes are required;
- broad stylesheet reformatting that creates noisy diffs;
- opening a PR before the core implementation is complete;
- continuing contents-API full-file edits after file output was truncated;
- surfacing routine recoverable connector conflicts to the user instead of resolving them internally.

When a previous PR is closed and superseded, inspect the failure reason before writing new changes so the replacement PR directly addresses the process gap.

## Agent skill runbooks

Repo-specific skill runbooks live under:

```text
.agents/skills/
```

Relevant skills include:

- `.agents/skills/github-issue-to-pr.md` for repeatable issue-to-PR execution;
- `.agents/skills/large-file-safe-editing.md` for safe handling of large or truncated files;
- `.agents/skills/github-pages-generator-changes.md` for generator, report rendering, RSS, manifest, and `_site/` boundaries;
- `.agents/skills/css-change-discipline.md` for narrow stylesheet work.

Use these runbooks before making related changes.

## Developer/operator tool selection

Prefer a tested repository-owned utility over a large bespoke external script when the task class is recurring or substantially duplicates an existing workflow. One-off investigation scripts remain acceptable where durable tooling would add more complexity than value.

Use the execution plane that matches the task:

- use `./tools/dev/cp-dev` for recurring working-tree setup, diagnostics, testing, validation, building, local serving and cleanup;
- use `tools/operator/cp` for authoritative GitHub, protected-main, CI and publication evidence;
- when a repeated capability belongs in one of those planes but is missing, shape the smallest extension rather than repeatedly recreating a large script;
- use a bounded temporary command or script only for a genuinely one-off local observation;
- stop and require separately governed design and authority for privileged mutation, workflow dispatch, merge, deployment, publication, credential changes or other administration capability.

`cp-dev` intentionally executes candidate working-tree code. Its output is developer validation only and must never be presented as trusted `CRYPTOPULSE_OPERATOR_EVIDENCE` merely because the command is repository-owned.

## Legacy low-level Git strategy

If direct lower-level Git object operations become fully available again, the following strategy remains acceptable:

1. Fetch the current `main` commit and tree.
2. Create a branch from the current `main` commit.
3. Prepare all changed file contents before writing anything.
4. Create blobs for every changed file.
5. Create a tree using the current `main` tree as the base and all changed paths as entries.
6. Create one commit with that tree and the current `main` commit as parent.
7. Update the branch ref once to point at the new commit.
8. Open one PR against `main`.

Avoid using per-file `update_file` calls for multi-file implementation work unless the preferred patch workflow and lower-level Git object operations are both unavailable or unsuitable.

For single-file documentation-only changes, a normal single-file commit is acceptable.

## Working from GitHub issues

When asked to work on an issue:

1. Fetch and read the issue body before editing.
2. Treat the issue acceptance criteria as the source of truth.
3. Keep the implementation scoped to the issue unless the user explicitly broadens scope.
4. Create a branch from the current `main` head.
5. Prefer branch names that reference the issue number.
6. Preserve all demo/disclaimer requirements.
7. Do not edit generated `_site/` output directly.
8. Open a PR against `main` only after the implementation is complete.
9. Include:

```text
Closes #<issue-number>
```

in the PR body.
10. Convert issue acceptance criteria into the PR checklist where practical.
11. State verification performed and any limitations.
12. Do not manually close the issue; allow GitHub to close it automatically when the PR merges.

Suggested branch naming examples:

```text
issue-6-landing-page-ux
issue-7-report-reading-ux
issue-8-archive-search-foundations
issue-11-ai-patch-workflow
```

## Branch naming

Use concise branch names such as:

```text
docs-add-agents-guidance
site-demo-disclaimer-update
fix-pages-build
reports-archive-index-fix
```

Prefer lowercase words separated by hyphens.

## Commit and PR style

Commit messages should be short and imperative:

```text
Add AGENTS guidance
Clarify demo disclaimer
Fix Pages archive rendering
```

PR bodies should include:

- summary;
- key changes;
- verification performed;
- any limitations or follow-up work.

If the PR implements an issue, include:

```text
Closes #<issue-number>
```

Suggested PR structure:

```markdown
## Summary

Closes #<issue-number>

## Changes

- ...

## Acceptance criteria covered

- [x] ...

## Verification

- ...

## Notes / limitations

- ...
```

## GitHub Pages architecture

Raw Markdown reports are the source of truth.

Generated `_site/` output is disposable and should not be edited directly.

The Pages site is generated by:

```text
scripts/build_pages_site.py
```

Static styling lives in:

```text
site/assets/cryptopulse.css
```

The deploy workflow is:

```text
.github/workflows/pages.yml
```

The AI patch workflow is:

```text
.github/workflows/apply-ai-patch.yml
```

The Pages workflow builds `_site/`, uploads it as a GitHub Pages artefact, and deploys via GitHub Actions.

## Files and responsibilities

- `reports/crypto/hourly/**/*.md`: raw generated report archive; preserve report body exactly unless the task explicitly asks to edit reports.
- `scripts/build_pages_site.py`: static site generator; update this for layout, page structure, RSS, manifest, archive, or report rendering changes.
- `site/assets/cryptopulse.css`: site styling; update this for visual changes.
- `_site/`: generated output; do not commit or edit as source.
- `.github/workflows/pages.yml`: Pages build/deploy workflow.
- `.github/workflows/apply-ai-patch.yml`: AI multi-file patch application workflow.
- `.agents/skills/**/*.md`: agent runbooks; update these when process guidance changes.
- `README.md`: public repository description and local build instructions.
- `AGENTS.md`: agent operating guidance.

## Demo disclaimer requirements

All public-facing surfaces should consistently communicate that CryptoPulse is a demo/prototype.

Preserve or strengthen wording that says:

- the site is a demo or prototype;
- reports are AI-generated examples;
- reports may be inaccurate, incomplete, stale, misleading, or hallucinated;
- the content is not financial advice;
- the content is not investment research;
- the content is not a recommendation;
- the content is not a trading signal;
- users should not rely on the reports for trading, investing, or risk decisions.

This applies to:

- homepage;
- latest report page;
- individual report pages;
- archive pages;
- footer disclaimers;
- RSS feed descriptions;
- manifest metadata;
- README wording.

## Local build and verification

Prepare the repository-local development environment:

```bash
./tools/dev/cp-dev bootstrap
```

Run the canonical unit-test suite when you need the test gate alone:

```bash
./tools/dev/cp-dev test
```

Run the normal local pre-PR mirror:

```bash
./tools/dev/cp-dev check
```

Build and inspect the disposable site with the stable developer commands:

```bash
./tools/dev/cp-dev build
./tools/dev/cp-dev serve
```

Then open:

```text
http://localhost:8000
```

Stop the server with `Ctrl+C`. Remove generated site output and allowlisted Python caches with:

```bash
./tools/dev/cp-dev clean
```

`cp-dev` executes the current working tree and does not produce trusted operator evidence. For authoritative GitHub/CI state, use the separately governed operator toolkit.

For small documentation-only changes, local build is not required.

For changes to the generator, CSS, workflow, report rendering, RSS, or manifest, run or reason through the Pages build and state any verification limits in the PR body.

## Deployment checks

After merging a Pages-affecting PR, check:

1. GitHub Actions workflow `Publish CryptoPulse Pages` has run.
2. The build job completed.
3. The deploy job completed.
4. The public Pages URL is expected to be:

```text
https://8ft0-ai.github.io/crypto-pulse/
```

If live web access is unavailable, report that limitation clearly and verify repository/workflow state instead.

## Report handling rules

Do not rewrite archived reports for style unless explicitly asked.

The archive process should preserve raw generated report bodies and add YAML front matter only when required.

Render-only cleanup, such as removing ChatGPT citation tokens from public HTML, belongs in `scripts/build_pages_site.py`, not in the raw Markdown archive.

## Design principles

Keep the site polished but unmistakably a demo.

Good design direction:

- clear demo banner;
- visible AI-generated labels;
- visible not-for-trading language;
- readable report layout;
- simple archive navigation;
- mobile-friendly styling;
- machine-readable RSS and manifest metadata.

Avoid language that makes the site sound like a live research product, signal provider, or investment service.

Prefer:

```text
AI-generated demo crypto market report examples
```

Avoid:

```text
crypto market intelligence service
trading signals
recommendations
investment research
```

## Safety and compliance posture

Crypto markets are volatile and high risk. The site should not encourage trading behaviour.

Do not add content that implies:

- verified market accuracy;
- profitable predictions;
- actionable trading advice;
- personalised financial guidance;
- professional investment research coverage.

## Useful PR checklist

Before opening a PR, check:

- [ ] Branch is based on current `main`.
- [ ] Only intended files changed.
- [ ] Generated `_site/` output was not committed.
- [ ] Demo disclaimer language is preserved.
- [ ] README and public metadata remain consistent if positioning changed.
- [ ] For issue work, all acceptance criteria are addressed before PR creation.
- [ ] PR body explains verification performed or limitations.
