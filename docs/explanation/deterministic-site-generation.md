# Deterministic site generation

> **Mode:** Explanation  
> **Audience:** CryptoPulse architects, contributors and reviewers  
> **Outcome:** Understand why Markdown reports and checked-in assets remain the source of truth while `_site/` is rebuilt as disposable output.

CryptoPulse separates report content from its web presentation. Archived Markdown records what the repository accepted as report source content. The static-site generator transforms that archive into a navigable site for readers, but the transformation does not make the generated HTML a second source of truth.

## One source, many derived views

A report can appear in several generated forms:

- an individual archive page;
- the latest-report page;
- a homepage card;
- an archive listing;
- a search record;
- a manifest entry;
- an RSS item.

Storing each form independently would allow them to drift. A title could change in one index but not another, or an old HTML page could survive after its source report was removed.

The build instead parses the Markdown archive once and derives every view from the same report objects. This keeps navigation, metadata and URLs aligned with the source archive.

## Clean builds prevent stale output

The generator removes the existing `_site/` directory before writing a new one. This matters because incremental copying alone cannot reliably prove that an obsolete generated file should still exist.

A clean build establishes a simpler invariant:

```text
_site after the build = output derived from the current repository sources
```

Anything not reproduced by the current build disappears.

## Repository code owns presentation boundaries

The report Markdown supplies source content. Repository code adds the public-facing frame:

- demo and non-advice notices;
- site navigation;
- metadata panels;
- source presentation;
- archive pagination;
- responsive styling;
- search and filter metadata.

This keeps product and safety boundaries consistent across reports rather than relying on each report author or model generation to reproduce them exactly.

The same principle applies to governed analysis: a model may provide accepted structured content, but repository code owns Markdown structure and site presentation.

## Stable path mapping supports traceability

The generator maps a report's relative path under `reports/crypto/hourly/` to the same relative path under `_site/archive/`, replacing `.md` with `.html`.

That predictable rule lets a reviewer move in both directions:

```text
source report → rendered page
rendered page → source report
```

It also allows tests and workflows to prove that an expected report path was rendered without searching the entire generated tree.

## Why `_site/` is not committed

Committing generated output would duplicate every source change with a large derived diff. Reviewers would need to determine whether the HTML was produced by the current generator or edited manually, and merge conflicts would mix source intent with build artefacts.

By keeping `_site/` uncommitted:

- pull requests review the source report, templates and generator changes directly;
- CI proves that the site can be rebuilt;
- deployment receives a freshly generated artefact;
- a manual edit to generated HTML cannot become canonical;
- stale pages are removed by the next clean build.

The repository's pull-request workflow explicitly rejects tracked `_site/` files and builds the site again as objective evidence.

## Deterministic does not mean frozen

The generator can evolve. Templates, styling, search metadata and report UX may change, causing the same report source to render differently under a new reviewed generator version.

The deterministic property is scoped to a repository state: given the same checked-in reports, assets, generator code and dependencies, the build follows the same ordered pipeline and produces the same path structure and content rules.

A site change therefore belongs in the source that caused it—report Markdown, site assets or generator code—not in `_site/`.

## Operational consequence

A contributor should:

1. edit or add canonical source files;
2. run `python -m site_generator`;
3. inspect the generated result;
4. run the repository tests;
5. leave `_site/` untracked and uncommitted;
6. let CI and the deployment workflow rebuild it.

For a guided example, see [Build and inspect CryptoPulse locally](../tutorials/build-and-inspect-cryptopulse-locally.md). For exact generated paths, see [Generated site artefacts](../reference/generated-site-artefacts.md).
