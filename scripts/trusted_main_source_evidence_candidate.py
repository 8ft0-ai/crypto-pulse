#!/usr/bin/env python3
"""Bounded public entry point for Phase 17 source-evidence candidate tooling."""

from __future__ import annotations

import trusted_main_source_evidence_candidate_impl as _impl

for _name, _value in vars(_impl).items():
    if _name not in {
        "__name__",
        "__loader__",
        "__package__",
        "__spec__",
        "render_pr_body",
        "main",
        "PR_BODY_SAFE_MAX_CHARS",
    }:
        globals()[_name] = _value

_ORIGINAL_RENDER_PR_BODY = _impl.render_pr_body
PR_BODY_SAFE_MAX_CHARS = 60_000


def render_pr_body(manifest, evidence, candidate_commit_sha):
    """Render deterministic review prose without duplicating exact recovery rows."""
    recoveries = [
        row
        for row in manifest.get("applied_recovery_decisions", [])
        if isinstance(row, dict)
    ]
    summary_manifest = dict(manifest)
    summary_manifest["applied_recovery_decisions"] = []

    body = _ORIGINAL_RENDER_PR_BODY(
        summary_manifest,
        evidence,
        candidate_commit_sha,
    )

    if recoveries:
        class_counts: dict[str, int] = {}
        for row in recoveries:
            blocker_class = str(row.get("blocker_class") or "unknown")
            class_counts[blocker_class] = class_counts.get(blocker_class, 0) + 1

        marker = "## Recovery decisions\n\n- None supplied/applied.\n"
        classes = ", ".join(
            f"`{name}={class_counts[name]}`"
            for name in sorted(class_counts)
        )
        replacement = (
            "## Recovery decisions\n\n"
            f"- Applied recovery count: `{len(recoveries)}`.\n"
            f"- Recovery classes: {classes}.\n"
            "- Exact recovery details remain in "
            f"`{evidence['prepared_artifact_name']}/accumulation-manifest.json`; "
            f"candidate ID `{manifest['candidate_id']}` binds the exact recovery inputs.\n"
        )

        if marker not in body:
            raise _impl.CandidateError(
                "unable to locate recovery section while bounding PR body"
            )
        body = body.replace(marker, replacement, 1)

    if len(body) > PR_BODY_SAFE_MAX_CHARS:
        raise _impl.CandidateError(
            "candidate PR body exceeds safe limit "
            f"of {PR_BODY_SAFE_MAX_CHARS} characters"
        )
    return body


_impl.render_pr_body = render_pr_body
_impl.PR_BODY_SAFE_MAX_CHARS = PR_BODY_SAFE_MAX_CHARS


def main():
    return _impl.main()


if __name__ == "__main__":
    raise SystemExit(main())
