# Contribute documentation

> **Mode:** How-to  
> **Audience:** Contributors and maintainers  
> **Outcome:** Add or revise a CryptoPulse documentation page without mixing user needs, breaking repository links or moving evidence into the wrong domain.

## Choose the primary reader need

Before editing, state the one result the page should deliver.

Use a tutorial when a new reader needs a guided learning sequence with an observable outcome. Use a how-to guide when a competent reader needs to complete one concrete task. Use reference when the reader needs precise facts, supported values, paths, commands or contracts. Use explanation when the reader needs architecture, rationale or trade-offs.

If the source material serves several needs, split and rewrite it. Do not copy the same paragraphs into several modes.

## Put the page in the correct repository domain

Place current human documentation under one of these paths:

```text
docs/tutorials/
docs/how-to/
docs/reference/
docs/explanation/
```

Do not move the following into `docs/`:

```text
planning/    roadmap, delivery and decision records
evaluation/  evaluation evidence and reviewed decisions
tests/       tests, fixtures and test-specific notes
schemas/     machine-readable contracts
prompts/     versioned prompt artefacts
config/      executable configuration
reports/     report source content
analysis/    accepted generated analysis artefacts
```

Agent instructions and contribution templates remain under `AGENTS.md`, `.agents/` and `.github/`.

## Add the required page metadata

Begin with one H1 title followed by a visible metadata block:

```markdown
# Page title

> **Mode:** How-to  
> **Audience:** Project operators  
> **Outcome:** Build the generated site from checked-in report data.
```

Use lower-case, hyphenated filenames. Use Australian English and the repository term `artefact`.

Do not put issue status, implementation-record wording or pull-request close conditions in a current documentation page. Preserve that history in planning, evaluation, issues, pull requests and Git history.

## Write for the selected mode

### Tutorial

- Begin from a known state.
- Keep the path linear and safe.
- Produce a visible success.
- Avoid optional branches and exhaustive detail.
- Use checked-in data where practical.

### How-to

- Name one practical goal.
- Assume the reader understands the basic system context.
- Include only the steps and checks needed for that goal.
- Link to reference instead of reproducing large field or path catalogues.

### Reference

- Use neutral language.
- Prefer tables, definitions and explicit constraints.
- Link directly to schemas, configuration, workflows, prompts, source code and tests.
- Exclude delivery narrative and architectural persuasion.

### Explanation

- Describe why the system is designed as it is.
- Discuss boundaries, trade-offs and consequences.
- Link to procedures and reference rather than embedding long command sequences or exhaustive field tables.

## Keep links stable and relative

Use repository-relative Markdown links. Check them from the location of the source page, not from the repository root.

When moving a page:

1. search for every incoming reference to the old path;
2. update valid internal links in the same pull request;
3. remove the obsolete duplicate after links are updated;
4. retain a short compatibility page only when the old path is likely to be an important external link;
5. make the compatibility page point to one canonical destination and do not duplicate the original content.

Link to canonical repository artefacts instead of copying them. For example, a reference page should link to the relevant file under `schemas/`, `config/` or `.github/workflows/`.

## Update the documentation index

Add the new page to [`docs/index.md`](../index.md) under the reader task and documentation mode that best match its purpose. Do not add links to pages that are planned but do not yet exist.

Every Markdown page under the four canonical mode directories must appear exactly once in its matching mode catalogue. A page may also be linked contextually from a reader-task section.

## Validate the change

Run the repository baseline:

```bash
python -m unittest discover -s tests
python scripts/validate_documentation.py
python -m site_generator
```

The documentation validator objectively checks:

- tracked internal Markdown links, local image targets and heading anchors;
- repository-relative path safety;
- references to declared removed document paths;
- that every mode-catalogue destination is a tracked canonical page in the expected directory;
- that every canonical page appears exactly once in the matching `docs/index.md` mode catalogue;
- exactly one H1 and visible `Mode`, `Audience` and `Outcome` metadata on canonical pages;
- agreement between a canonical page's declared mode and its directory;
- lower-case, hyphenated canonical page filenames;
- accidental tracked `_site/` output.

These structural requirements apply only to canonical pages under `docs/tutorials/`, `docs/how-to/`, `docs/reference/` and `docs/explanation/`. Compatibility pointers, planning records, evaluation evidence, READMEs and fixture notes are not required to use canonical page metadata.

The validator does not assess prose quality, test whether the selected mode is editorially appropriate or decide whether an architectural explanation is correct.

Also confirm that commands match current repository behaviour, historical evidence remains preserved, no product boundary changed and `_site/` was not staged or committed.

Record validation evidence and old-to-new path mappings in the pull-request body.

## Review the page as a reader

Before opening the pull request, answer these questions:

- Can the intended reader find the page from `docs/index.md`?
- Does the page solve or explain one primary need?
- Is procedural detail separated from exhaustive reference and conceptual explanation?
- Are links, commands and repository paths exact?
- Is any paragraph unnecessarily duplicated elsewhere?
- Does current guidance avoid historical issue-status wording?

The migration plan and complete conventions are recorded in [`planning/documentation/diataxis-migration.md`](../../planning/documentation/diataxis-migration.md).
