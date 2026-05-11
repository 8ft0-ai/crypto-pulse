# Main branch protection

This repository uses pull-request based delivery for site and process changes. Generated report archives may still be committed directly only when explicitly required by the report-archive recovery workflow.

## Recommended protection for `main`

Configure this manually in GitHub:

```text
Settings → Branches → Branch protection rules → Add rule
Branch name pattern: main
```

Recommended settings:

- Enable **Require a pull request before merging**.
- Enable **Require status checks to pass before merging**.
- Select the required check: `Build site and check generated output` from `Validate CryptoPulse PR`.
- Enable **Require branches to be up to date before merging** if this does not create too much friction.
- Enable **Do not allow bypassing the above settings** where practical.
- Restrict who can push to matching branches if direct pushes to `main` should be fully blocked.

## Direct-to-main exception

Direct commits to `main` should be narrow and intentional. Accepted exceptions are:

1. Hourly report archive commits generated from recovery packages.
2. Explicitly approved emergency fixes.
3. Explicitly approved repository administration.

All feature, UX, site-generator, workflow, and documentation improvements should use:

```text
issue → branch → implementation → pull request → merge
```

## Required PR validation

The repository includes `.github/workflows/pr-validation.yml`, which runs on pull requests that touch reports, site files, scripts, workflows, documentation, or the README.

The workflow checks that:

- Python dependencies install cleanly;
- the current site build wrapper runs successfully;
- expected generated artefacts exist after the build;
- committed `_site/` generated output is rejected.

## Why `_site/` must not be committed

`_site/` is disposable generated output. The source of truth is:

- raw Markdown reports under `reports/`;
- source assets under `site/`;
- build scripts under `scripts/`;
- GitHub Actions workflows under `.github/workflows/`.

Committing `_site/` makes reviews noisy, risks stale generated content, and weakens confidence that GitHub Pages is deploying from a clean build.
