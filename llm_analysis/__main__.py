from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import load_json, process_analysis


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and deterministically render governed CryptoPulse analysis")
    parser.add_argument("evidence_bundle")
    parser.add_argument("analysis")
    parser.add_argument("--schemas-dir", default="schemas")
    parser.add_argument("--markdown-output")
    parser.add_argument("--normalised-output")
    args = parser.parse_args()

    schemas = Path(args.schemas_dir)
    result = process_analysis(
        load_json(args.evidence_bundle),
        load_json(args.analysis),
        evidence_schema=load_json(schemas / "crypto-market-evidence-bundle-v1.json"),
        analysis_schema=load_json(schemas / "crypto-market-analysis-v1.json"),
    )
    print(json.dumps(result.report.as_dict(), indent=2, sort_keys=True))
    if not result.report.is_valid:
        for output in (args.markdown_output, args.normalised_output):
            if output:
                Path(output).unlink(missing_ok=True)
        return 2
    if args.markdown_output:
        Path(args.markdown_output).write_bytes(result.markdown or b"")
    if args.normalised_output:
        Path(args.normalised_output).write_bytes(result.normalised_analysis or b"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
