# Optional LLM narrative layer boundary

This document records the design decision for issue #82. It does not implement LLM calls, select a paid provider, add secrets, generate `_site/` output, or change the deterministic report generator.

## Recommendation

Do not add an LLM narrative layer yet.

The deterministic evidence spine now exists in design and implementation form, but the scheduled `valid-ok` snapshot proof remains unproven in issue #78. Until the source-evidence flow is proven end-to-end and deterministic report PRs have been exercised against real validated snapshots, an LLM narrative layer would add operational and governance risk before the baseline is stable.

Revisit this decision only after:

1. the scheduled or dispatched snapshot workflow has produced a `valid-ok` source snapshot PR with embedded `quality.status`;
2. a deterministic report PR has been generated from that validated snapshot;
3. reviewers have confirmed the deterministic report is useful without narrative embellishment;
4. governance has agreed that optional prose adds enough customer value to justify model, prompt, validation, and secrets overhead.

## Potential value beyond deterministic summaries

An LLM layer could add value only as a readability layer over already validated evidence. Potential value includes:

- smoother prose for readers who find tables hard to scan;
- clearer explanation of why a report is degraded;
- concise reader-facing transitions between deterministic sections;
- summarisation of source-status limitations in plainer language;
- highlighting relationships already explicit in the snapshot, such as a market table and an exchange cross-check table agreeing or disagreeing.

The LLM must not become a source of market facts. It must not fetch external data, infer unsupported causes, predict prices, create trading recommendations, or personalise advice.

## Eligible and ineligible report sections

The following sections must remain deterministic:

- YAML front matter;
- product-boundary and non-investment-advice notice;
- snapshot quality status;
- required source statuses;
- optional exchange statuses;
- market summary table;
- DeFi and stablecoin table;
- selected exchange rows;
- evidence and source status section;
- scope limitations;
- any warning, error, source, timestamp, price, market-cap, volume, or percentage-change value.

The following sections could be eligible for optional LLM prose in a future implementation:

- a short plain-English overview after the deterministic quality section;
- a short explanation of degraded status using only validator warnings;
- a short summary of what the deterministic market table records;
- a short source-evidence note explaining which sources were used and which were skipped.

Even in eligible sections, the LLM output must be treated as draft prose and must be reviewable before merge.

## Grounding requirements for any future prompt

A future prompt must be grounded strictly in a compact evidence bundle created from the validated snapshot and deterministic report. The bundle should include:

- source snapshot path;
- generated report path;
- `quality.status`;
- blocking issues;
- non-blocking warnings;
- source statuses and fetched timestamps;
- market table rows for configured assets;
- DeFi and stablecoin rows;
- selected exchange cross-check rows;
- mandatory product-boundary and non-investment-advice wording;
- explicit prohibited language.

The prompt must instruct the model to:

- use only the provided evidence bundle;
- preserve source references and snapshot path references;
- avoid unsupported causes, predictions, recommendations, or implications;
- avoid target prices, buy/sell/hold calls, and personalised advice;
- emit draft text only for the explicitly eligible prose slots;
- return a structured response that can be validated field-by-field.

## Citation and source-reference preservation

A future LLM layer must not invent citations. Source references should remain deterministic and should point back to:

- the exact source snapshot path;
- the source status table;
- the deterministic report section being summarised.

If the model mentions a fact, that fact must be traceable to a field in the evidence bundle. If a fact cannot be traced, validation should fail.

## Disclaimer and product-boundary enforcement

The deterministic disclaimer must remain outside the model’s control. The LLM must not rewrite, shorten, or relocate it.

Generated prose must be rejected if it contains or implies:

- financial advice;
- investment research;
- target prices;
- buy, sell, or hold instructions;
- trading signals;
- personalised portfolio actions;
- unsupported market causality;
- claims about future returns or risk-adjusted performance.

## Hallucination and advice-leakage checks

A future implementation would need validation before any PR is opened. Minimum checks should include:

- deterministic diff boundaries so only approved prose slots can change;
- banned-phrase checks for trading and advice language;
- numeric consistency checks so all prices, percentages, ranks, and timestamps match the deterministic report;
- source-reference checks so every named source exists in the snapshot;
- unsupported-claim checks using an allow-list of permitted evidence fields;
- reviewer-visible prompt, evidence bundle, model identifier, and output in the PR body or an attached artefact;
- hard fallback to deterministic-only output when validation fails.

## Draft-only and PR review policy

If this capability is later approved, LLM prose should be draft-only. It should open a PR and require human review. It should not auto-merge, auto-publish, or write directly to `main`.

The PR should clearly show:

- the deterministic report path;
- the source snapshot path;
- the evidence bundle used;
- model/provider identifier;
- prompt template version;
- validation checks performed;
- generated prose diff;
- fallback behaviour if the LLM was unavailable or rejected.

## Model, provider, and secrets policy

A future implementation would require an explicit model/provider decision and a secrets policy before coding. At minimum:

- no API keys or credentials may be committed;
- provider credentials must use repository or organisation secrets;
- the workflow must fail closed when secrets are unavailable;
- model/version must be pinned or recorded;
- prompt template version must be recorded;
- provider data-retention and confidentiality posture must be reviewed before use;
- generated prose must remain reproducible enough for governance review, even if exact model outputs are not perfectly deterministic.

No provider should be added as part of this issue.

## Fallback behaviour

If the future LLM step fails, times out, is unavailable, lacks secrets, or fails validation, the system should:

1. keep the deterministic report unchanged;
2. record that optional narrative was skipped;
3. avoid opening a prose-change PR unless there is useful diagnostic evidence;
4. never block deterministic report generation solely because optional narrative failed.

## Decision

Do not proceed with implementation now.

Create follow-up implementation issues only after the deterministic snapshot and report workflows have been proven with real generated PR evidence and after product/governance review confirms that optional prose is worth the additional controls.
