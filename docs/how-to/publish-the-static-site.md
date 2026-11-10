# Publish the static site

> **Mode:** How-to  
> **Audience:** CryptoPulse operators and maintainers  
> **Outcome:** Publish the current `main` site through the repository's GitHub Pages workflow and confirm the deployment completed.

Publication uses [`.github/workflows/pages.yml`](../../.github/workflows/pages.yml). The workflow builds `_site/` in GitHub Actions, uploads it as a Pages artefact and deploys it through the `github-pages` environment. It does not commit generated output.

## Configure GitHub Pages

In the repository settings, select:

```text
Settings → Pages → Build and deployment → Source → GitHub Actions
```

The workflow requires these permissions:

```text
contents: read
pages: write
id-token: write
```

## Publish through a normal merge

The workflow runs after a push to `main` that changes a configured site input, including:

```text
reports/crypto/hourly/**/*.md
site/**
site_generator/**
scripts/build_pages_site.py
scripts/build_pages_site_with_search.py
scripts/build_pages_site_mobile_ux.py
scripts/build_pages_site_brief_glance.py
scripts/build_pages_site_search_filters.py
.github/workflows/pages.yml
```

Merge the reviewed pull request normally. Do not add `_site/` to the branch.

## Run publication manually

To rebuild and publish current `main` without a matching path change:

1. Open **Actions**.
2. Select **Publish CryptoPulse Pages**.
3. Choose **Run workflow**.
4. Select `main`.
5. Start the run.

GitHub CLI equivalent:

```bash
gh workflow run pages.yml --ref main
```

## Review the workflow

Confirm that:

1. the `build` job checked out the intended `main` commit;
2. `python -m site_generator` passed;
3. the Pages artefact upload passed with `_site` as the upload path;
4. the `deploy` job completed in the `github-pages` environment;
5. the deployment URL in the job summary is the expected CryptoPulse Pages site.

The expected public root is:

```text
https://8ft0-ai.github.io/crypto-pulse/
```

## Verify the deployed result

After deployment, use [Verify the live site](verify-the-live-site.md). That workflow checks the public homepage, latest report, archive and search pages with a real browser and retains review evidence.

## Handle failure

- If the build fails, reproduce it locally with `python -m site_generator` and correct the source branch through a pull request.
- If artefact upload fails, inspect the Actions error and confirm `_site/` was generated during the job.
- If deployment fails after a successful build, inspect the Pages environment, permissions and repository Pages setting.
- Do not commit `_site/` as a workaround for a failed Pages build.

For local proof before publication, see [Build the static site](build-the-static-site.md). For the generated-output contract, see [Generated site artefacts](../reference/generated-site-artefacts.md).
