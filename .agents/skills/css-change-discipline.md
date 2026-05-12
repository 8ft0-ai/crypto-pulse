# CSS change discipline

Use this skill before changing `site/assets/cryptopulse.css` or any future stylesheet in this repository.

## Goal

Keep CSS diffs minimal, readable, and easy to review. Styling changes should support the requested UI change without creating broad conflicts or obscuring the implementation.

## Rules

- Keep stylesheet changes narrow.
- Avoid whole-file reformatting.
- Do not compress existing multi-line CSS blocks into one-line blocks.
- Do not reorder unrelated selectors.
- Add component styles near related components or under a clearly labelled section.
- Preserve the existing visual system unless the issue explicitly asks for a redesign.
- Avoid changing global selectors, resets, typography, colour variables, or layout primitives unless required.
- Check mobile and print media sections when the changed component appears there.
- Do not use CSS to fake a missing generator or markup implementation.

## Review discipline

Before opening a PR, inspect the CSS diff and remove unrelated churn. If a selector is changed only because of formatting, revert it.

For UX issues involving generated pages, confirm the generator emits the necessary markup and the CSS is only the styling layer.

## PR notes

For CSS-affecting PRs, include concise verification notes describing the affected surface and whether mobile or print rules were considered.
