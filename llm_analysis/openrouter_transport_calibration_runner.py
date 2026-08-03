"""Protected CLI for the Phase 8 observable OpenRouter transport calibration."""
from __future__ import annotations

import argparse
import json
import os
import sys

from .evaluation import EvaluationIntegrityError
from .openrouter_transport_calibration import (
    DEFAULT_CONFIG,
    CalibrationConfigurationError,
    execute_transport_calibration,
    prepare_transport_calibration,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--repository-root", default=".")
    prepare.add_argument("--config", default=DEFAULT_CONFIG)
    prepare.add_argument("--output-dir", required=True)
    run = commands.add_parser("run")
    run.add_argument("--repository-root", default=".")
    run.add_argument("--config", default=DEFAULT_CONFIG)
    run.add_argument("--prepared-dir", required=True)
    run.add_argument("--output-dir", required=True)
    run.add_argument("--trusted-main-sha")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare_transport_calibration(
                repository_root=args.repository_root,
                config_path=args.config,
                output_dir=args.output_dir,
            )
        else:
            result = execute_transport_calibration(
                repository_root=args.repository_root,
                config_path=args.config,
                prepared_dir=args.prepared_dir,
                output_dir=args.output_dir,
                api_key=os.environ.get("OPENROUTER_API_KEY"),
                trusted_main_sha=args.trusted_main_sha,
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (
        CalibrationConfigurationError,
        EvaluationIntegrityError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        secret = os.environ.get("OPENROUTER_API_KEY", "")
        message = " ".join(str(exc).split())[:500]
        if secret:
            message = message.replace(secret, "[REDACTED]")
        print(f"Phase 8 transport calibration failed: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
