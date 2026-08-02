"""Canonical entrypoint for writing or checking the retained Slice 5 proof."""
from __future__ import annotations

import argparse
from pathlib import Path

from . import candidate_selection_evaluation as evaluation
from .candidate_selection_proof_support import fail
from .candidate_selection_validation_proof import validation_matrix


def evaluate_candidate_selection_proof(*args, **kwargs):
    """Evaluate with explicit evaluation-only invalid-selection fixtures."""

    original = evaluation.validation_matrix
    evaluation.validation_matrix = validation_matrix
    try:
        return evaluation.evaluate_candidate_selection_proof(*args, **kwargs)
    finally:
        evaluation.validation_matrix = original


def main() -> int:
    parser = argparse.ArgumentParser(description="Write or verify Slice 5 selector proof")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(args.repository_root).resolve()
    proof = evaluate_candidate_selection_proof(root)
    for relative, content in proof.outputs.items():
        path = root / relative
        if args.check:
            if not path.is_file() or path.read_bytes() != content:
                fail("generated_output_drift", relative, "checked-in proof differs")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
