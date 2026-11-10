# Build the static site

> **Mode:** How-to  
> **Audience:** CryptoPulse contributors and operators  
> **Outcome:** Generate and verify the local `_site/` output from the current checked-in report archive.

## Prepare the local environment

From the repository root:

```bash
./tools/dev/cp-dev bootstrap
```

The canonical build requires the repository source, PyYAML and Python-Markdown. `bootstrap` creates the repository-local `.venv` and installs the declared dependencies from `requirements-dev.txt`; it does not require market-data credentials or an LLM provider secret.

## Run the canonical build

```bash
./tools/dev/cp-dev build
```

`build` runs the underlying `.venv/bin/python -m site_generator` command from the resolved repository root. The package entry point calls `site_generator.pipeline.build()`, which removes any existing `_site/` directory and rebuilds it from the current Markdown archive and site assets.

## Verify the required output

```bash
test -f _site/index.html
test -f _site/latest.html
test -f _site/archive/index.html
test -f _site/search.html
test -f _site/manifest.json
test -f _site/search-index.json
test -f _site/feed.xml
```

To verify one known source-to-output mapping:

```bash
test -f _site/archive/2026/05/09/1848_AEST_crypto_market_intelligence.html
```

## Inspect the result locally

```bash
./tools/dev/cp-dev serve
```

Open `http://localhost:8000/`, then inspect `latest.html`, `archive/` and `search.html`. Use `--port <port>` for another loopback port in the range 1024–65535. `serve` never builds implicitly.

## Run repository validation

For the unit-test suite alone:

```bash
./tools/dev/cp-dev test
```

Before opening a pull request that can affect the site, run the full local pre-PR mirror:

```bash
./tools/dev/cp-dev check
```

`check` runs unit tests, documentation validation, the tracked-`_site` guard, site build and expected-artefact verification. GitHub Actions remains authoritative for PR acceptance.

Confirm that `_site/` is not tracked or staged when diagnosing Git state directly:

```bash
git ls-files _site
git diff --cached --name-only -- _site
```

Both commands must produce no output.

## Remove generated output

Stop any local server with `Ctrl+C`, then run:

```bash
./tools/dev/cp-dev clean
```

`clean` removes `_site/` and allowlisted Python cache artefacts only after validating all deletion candidates. It preserves `.venv`, Git metadata, source data, reports, worktrees, credentials and unrelated ignored files.

Do not commit `_site/`. GitHub Actions rebuilds the output for validation and deployment.

For a guided first build, see [Build and inspect CryptoPulse locally](../tutorials/build-and-inspect-cryptopulse-locally.md). For output paths and formats, see [Generated site artefacts](../reference/generated-site-artefacts.md).
