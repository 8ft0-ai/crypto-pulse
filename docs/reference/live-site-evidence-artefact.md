# Live-site evidence artefact

> **Mode:** Reference  
> **Audience:** CryptoPulse operators, reviewers and workflow maintainers  
> **Outcome:** Look up the contents, retention and interpretation of the post-deployment browser evidence bundle.

## Producer

| Property | Value |
| --- | --- |
| Workflow | [`.github/workflows/verify-live-pages.yml`](../../.github/workflows/verify-live-pages.yml) |
| Workflow name | `Verify CryptoPulse Live Pages` |
| Artefact name | `cryptopulse-live-site-evidence` |
| Retention | 30 days |
| Repository effect | None; evidence is uploaded to GitHub Actions and is not committed. |

## Files

| File | Purpose |
| --- | --- |
| `result.json` | Primary structured summary of page, navigation and CryptoPulse-specific assertions. |
| `accessibility.json` | Axe accessibility results used to identify serious or critical violations. |
| `homepage.html` | Captured rendered homepage HTML. |
| `homepage.txt` | Visible homepage text. |
| `homepage.png` | Full-page homepage screenshot. |
| `latest-report.html` | Captured rendered latest-report HTML. |
| `latest-report.txt` | Visible latest-report text. |
| `latest-report.png` | Full-page latest-report screenshot. |
| `archive.html` | Captured rendered archive HTML. |
| `archive.txt` | Visible archive text. |
| `archive.png` | Full-page archive screenshot. |
| `search.html` | Captured rendered search-page HTML. |
| `search.txt` | Visible search-page text. |
| `search.png` | Full-page search-page screenshot. |

## Recorded checks

The workflow records or asserts:

```text
HTTP status
page title
primary heading
skip-link presence
accessible link and button names
primary navigation state
serious or critical Axe violations
```

CryptoPulse-specific assertions cover:

```text
recent archive time and timezone
absence of Data not specified
no duplicated BTC/ETH metric groups
no disclaimer boilerplate as the latest headline
absence of the invalid ETH, L2s, DeFi majors metric value
```

A required assertion failure fails the workflow.

## Evidence priority

Review in this order:

1. `result.json` for the failing page and assertion;
2. `accessibility.json` for accessibility details;
3. visible-text capture for reader-facing content;
4. HTML capture for DOM structure;
5. screenshot for layout and visual confirmation.

The evidence describes the exact public deployment observed by the workflow. It does not replace the source files, build artefact or pull-request evidence that produced that deployment.

For operating steps, see [Verify the live site](../how-to/verify-the-live-site.md).
