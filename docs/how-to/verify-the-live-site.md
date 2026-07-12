# Verify the live site

> **Mode:** How-to  
> **Audience:** CryptoPulse operators and reviewers  
> **Outcome:** Run the post-deployment browser verification workflow and review the retained evidence for the public site.

Use this procedure after **Publish CryptoPulse Pages** completes successfully. The verification workflow is [`.github/workflows/verify-live-pages.yml`](../../.github/workflows/verify-live-pages.yml).

## Start the verification

A successful Pages deployment triggers the workflow automatically. To run it manually:

1. Open **Actions**.
2. Select **Verify CryptoPulse Live Pages**.
3. Choose **Run workflow**.
4. Select `main`.
5. Start the run.

## Check the workflow result

The browser run opens the public:

```text
homepage
latest report
archive
search page
```

Confirm that the `verify` job passed. A required assertion or serious/critical accessibility failure causes the workflow to fail.

## Download the evidence

Open the completed run and download:

```text
cryptopulse-live-site-evidence
```

The artefact is retained for 30 days.

Review `result.json` first. It is the primary machine-readable summary of HTTP, document, navigation and CryptoPulse-specific checks.

Then inspect:

```text
accessibility.json
homepage.txt
latest-report.txt
archive.txt
search.txt
homepage.png
latest-report.png
archive.png
search.png
```

Use the HTML captures when a text or screenshot result needs structural investigation.

## Review the required product checks

Confirm that the evidence shows:

- pages returned the expected HTTP response;
- titles and primary headings are present;
- skip links and named navigation controls are available;
- no serious or critical Axe violations remain;
- recent archive cards show time and timezone;
- `Data not specified` is absent;
- BTC and ETH metric groups are not duplicated within a card;
- disclaimer boilerplate is not promoted into the latest headline;
- the invalid legacy value `ETH, L2s, DeFi majors` is absent from ETH metrics.

## Respond to a failure

1. Identify the exact page and assertion in `result.json`.
2. Compare the visible-text, HTML, screenshot and accessibility evidence for that page.
3. Determine whether the problem is in source content, generator output, CSS/JavaScript or deployment state.
4. Correct the source through a scoped pull request.
5. Run local and pull-request validation.
6. Publish again and rerun live verification.

Do not edit the deployed HTML or commit `_site/` to repair the public site.

For the evidence-file catalogue, see [Live-site evidence artefact](../reference/live-site-evidence-artefact.md). For publication, see [Publish the static site](publish-the-static-site.md).
