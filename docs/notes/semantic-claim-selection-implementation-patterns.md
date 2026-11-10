# Semantic claim selection: implementation patterns and references

> **Status:** Companion working note to [Simplifying the semantic claim-plan pipeline](simplifying-semantic-claim-plan-pipeline.md).

## Forced tool selection

The remaining model interaction can be represented as a single forced tool:

```text
select_claims(
    selected_candidate_ids: array[candidate_id],
    maximum 8,
    unique items
)
```

For small candidate sets, candidate IDs can be represented as an enum. For larger sets, the repository can validate selections against a supplied lookup table.

The tool description should contain editorial criteria rather than the full semantic validator:

```text
Select the smallest set of materially useful, non-redundant
claim candidates for the report.

Prefer:
- material market movement;
- meaningful cross-source differences;
- explicit data-quality limitations;
- diversity across important subjects.

Do not select:
- routine successful source statuses unless needed;
- duplicate observations;
- an absolute observation already represented adequately
  by a selected comparison.
```

This is substantially simpler than asking the model to construct nested claims while reproducing all repository rules.

## Bounded retries

Retries can help after the task is simplified. Use a deterministic validator-feedback loop:

```text
attempt 1
    ↓
validate selected IDs and selection rules
    ↓
return exact machine-readable errors
    ↓
attempt 2
    ↓
accept or fail closed
```

Example feedback:

```json
{
  "errors": [
    {
      "code": "too_many_candidates",
      "maximum": 8,
      "actual": 11
    },
    {
      "code": "duplicate_subject_metric",
      "candidate_ids": ["claim-017", "claim-021"]
    }
  ]
}
```

A suitable boundary would permit:

- normal network and rate-limit retries;
- at most one semantic selection repair;
- no open-ended self-reflection loop;
- deterministic fallback or no report after the repair fails.

The feedback should come from repository validators, not an unconstrained model critique.

## Safe post-processing

Safe mechanical post-processing includes:

- removing duplicate candidate IDs;
- restoring canonical ordering;
- enforcing maximum claim counts;
- mapping candidate IDs back to repository-owned claims;
- deterministic section grouping;
- deterministic rendering.

Unsafe post-processing includes silently:

- relabelling intent;
- changing evidence operands;
- splitting a model-created claim;
- replacing evidence;
- changing comparison meaning.

Those semantic operations belong in candidate compilation before the model call.

## Groundedness and guardrails

Groundedness should be structural rather than judged only after generation. The model should never author the evidence reference, value, intent, relation or subject that defines the claim.

Useful guardrails include:

- exact candidate-ID validation;
- unique-selection enforcement;
- maximum selection count;
- redundancy-group limits;
- mandatory inclusion or exclusion rules where justified;
- deterministic fallback ranking;
- fail-closed behaviour when no valid selection is available;
- retained request, response, validation and reconstruction artefacts.

An LLM-based groundedness judge can be retained for diagnostics, but deterministic checks should remain authoritative wherever possible.

## Possible use of a second model

A second model is unnecessary for schema validity, evidence support or formal groundedness. Repository code can perform those checks more reliably.

A second model might help assess a subjective question such as whether a selected set is materially useful and non-redundant for the target reader. It should be introduced only if human evaluation shows that the deterministic baseline and primary selector regularly produce valid but unhelpful selections.

## How similar systems reduce model responsibility

Several established patterns support this direction:

- **Constrained decoding and parsing:** systems such as PICARD use a parser to reject invalid continuations rather than relying on the model to learn every formal rule from prose.
- **Content selection before realisation:** data-to-text systems commonly separate selection and planning from final language generation.
- **Function or tool calling:** application-owned tools expose a narrow parameter contract rather than asking the model to construct a large internal object.
- **Validator-guided retries:** libraries such as Instructor and Pydantic AI reflect deterministic validation failures back to the model under a bounded retry budget.
- **Iterative refinement:** research indicates that revision can improve first-pass outputs, but CryptoPulse should use repository-authored feedback rather than unconstrained self-critique.

## Suggested delivery sequence

```text
1. define the candidate schema
2. implement deterministic candidate compilation
3. test candidate recall over the frozen corpus
4. implement deterministic ranking baseline
5. define the minimal selection tool
6. implement selection validation and reconstruction
7. run the baseline without an LLM
8. smoke-test one or two models
9. compare usefulness, redundancy and stability
10. approve any repeated evaluation separately
```

## References

- OpenAI, [Structured outputs](https://platform.openai.com/docs/guides/structured-outputs)
- OpenAI, [Function calling](https://platform.openai.com/docs/guides/function-calling)
- Anthropic, [Implement tool use](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/implement-tool-use)
- Scholak et al., [PICARD: Parsing Incrementally for Constrained Auto-Regressive Decoding from Language Models](https://arxiv.org/abs/2109.05093)
- Puduppully et al., [Data-to-Text Generation with Content Selection and Planning](https://arxiv.org/abs/1809.00582)
- Madaan et al., [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651)
- Instructor, [Retrying](https://python.useinstructor.com/concepts/retrying/)
