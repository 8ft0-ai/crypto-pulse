# Governed LLM contract fixtures

These files are contract examples for Phase 5. The selected market values and source paths are based on `data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json`.

Hash, provider, model, usage, cost, and generation identifiers are deterministic fixture values used to exercise schema and contract relationships. They are not asserted as historical production provenance. The implementation delivered by later Phase 5 issues must calculate actual snapshot, prompt, completion, and evidence-bundle hashes from the bytes or canonical payload it processes, and must record provider metadata returned by the real request.

Invalid cases deliberately contain unsupported or unsafe content and must never be published or reused as market evidence.
