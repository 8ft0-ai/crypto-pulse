"""Public-data benchmark runner with OpenAI-compatible schema projection."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

from . import public_demo_benchmark as base
from . import public_demo_benchmark_compat as compat
from .evaluation import EvaluationConfigurationError, EvaluationIntegrityError
from .generation_config import ConfigurationError
from .openai_schema_projection import OpenAICompatibleSchemaClient


def execute_public_demo_projection(**kwargs: Any) -> dict[str, Any]:
    """Run the existing compatible demo with a provider-only schema adapter."""

    original_client = base.OpenRouterClient
    base.OpenRouterClient = OpenAICompatibleSchemaClient
    try:
        return compat.execute_public_demo_compat(**kwargs)
    finally:
        base.OpenRouterClient = original_client


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--repository-root", default=".")
    prepare.add_argument("--profile", default="config/llm-public-data-demo.yml")
    prepare.add_argument("--output-dir", required=True)
    run = sub.add_parser("run")
    run.add_argument("--repository-root", default=".")
    run.add_argument("--profile", default="config/llm-public-data-demo.yml")
    run.add_argument("--viability-config", default="config/llm-evaluation-viability.yml")
    run.add_argument("--prepared-dir", required=True)
    run.add_argument("--output-dir", required=True)
    run.add_argument("--trusted-main-sha")
    args = parser.parse_args()

    try:
        if args.command == "prepare":
            plan, cases = base.prepare_public_demo(
                repository_root=args.repository_root,
                profile_path=args.profile,
                output_dir=args.output_dir,
            )
            print(
                json.dumps(
                    {
                        "model": plan.model.model,
                        "cases": len(cases),
                        "maximum_logical_calls": plan.maximum_logical_calls,
                    },
                    sort_keys=True,
                )
            )
        else:
            summary = execute_public_demo_projection(
                repository_root=args.repository_root,
                profile_path=args.profile,
                viability_config_path=args.viability_config,
                prepared_dir=args.prepared_dir,
                output_dir=args.output_dir,
                api_key=os.environ.get("OPENROUTER_API_KEY"),
                trusted_main_sha=args.trusted_main_sha,
            )
            print(json.dumps(summary["decision"], sort_keys=True))
        return 0
    except (
        EvaluationConfigurationError,
        EvaluationIntegrityError,
        ConfigurationError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        secret = os.environ.get("OPENROUTER_API_KEY", "")
        message = compat.safe_provider_diagnostic(exc, secret)
        print(f"public demo schema-projection benchmark failed: {message}", file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
