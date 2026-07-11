"""Secret-aware CLI for the protected Phase 5 model evaluation workflow."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .evaluation import execute_evaluation
from .evidence_bundle import EvidenceBundleError
from .generation_config import ConfigurationError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--config", default="config/llm-evaluation.yml")
    parser.add_argument("--prepared-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--trusted-main-sha")
    args = parser.parse_args()

    secret = os.environ.get("OPENROUTER_API_KEY")
    try:
        summary = execute_evaluation(
            repository_root=Path(args.repository_root),
            config_path=args.config,
            prepared_dir=Path(args.prepared_dir),
            output_dir=Path(args.output_dir),
            api_key=secret,
            trusted_main_sha=args.trusted_main_sha,
        )
        print(json.dumps(summary["decision"], sort_keys=True))
        return 0
    except (EvidenceBundleError, ConfigurationError, OSError, ValueError, TypeError) as exc:
        message = " ".join(str(exc).split())[:500]
        if secret:
            message = message.replace(secret, "[REDACTED]")
        print(json.dumps({"status": "failed", "error": message}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
