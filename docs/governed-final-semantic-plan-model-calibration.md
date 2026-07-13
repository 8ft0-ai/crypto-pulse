# Final semantic claim-plan model calibration

Issue #269 adds one final compatibility calibration after run `29235513924` identified two correctable integration boundaries. GPT-5.6 completed the real contract but cross-source spot prices used inconsistent field names. Nex N2 Mini required a user-role message in addition to the governed system prompt. MiniMax M3 does not advance because its completed plan failed the semantic intent taxonomy.

## Scope

The final run contains exactly two substantive generations:

```text
GPT-5.6 Sol:  one route probe + one full-contract call
Nex N2 Mini: one route probe + one full-contract call
whole-run ceiling: USD 0.25
```

GPT-5.6 retains its USD 0.15 per-call ceiling. Nex retains a USD 0.02 per-call ceiling. The combined model ceilings are USD 0.21, leaving USD 0.04 beneath the hard whole-run boundary.

## Evidence normalisation

Before either call, the frozen smoke-case bundle is copied into a derived protected directory. Coinbase Exchange USD spot records whose source field is `price` are mapped to the canonical measure `price_usd`. Source identity, source path, subject, observed time, value and unit are unchanged. The derived bundle receives a recomputed content-addressed bundle ID, and the exact transformation is retained in `evidence-normalisation.json`.

## Nex request compatibility

The governed system message remains unchanged. For Nex N2 Mini only, the transport adds one minimal user-role execution message when the request otherwise contains no user message. Existing user messages are never duplicated.

## Scoring boundary

Semantic coverage, materiality, restraint and repeat stability are available only after the canonical validator accepts the plan. Missing or rejected plans are reported as unscored with null quality metrics. Empty failures cannot earn stability points.

## Trust boundary

The workflow is manual, trusted-main, read-only, protected-environment and artefact-only. It cannot publish analysis or update repository state. After merge, dispatch **Governed final semantic plan model calibration** once from `main`.
