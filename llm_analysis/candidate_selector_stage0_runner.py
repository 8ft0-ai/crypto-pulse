"""Fail-closed CLI for the Phase 7 low-cost candidate-selector Stage 0 screen."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

from .candidate_selector_stage0 import execute_stage0, prepare_stage0
from .candidate_selector_stage0_config import DEFAULT_STAGE0_CONFIG
from .contracts import canonical_json_bytes
from .evaluation import EvaluationConfigurationError, EvaluationIntegrityError
from .generation_config import GenerationConfig
from .openrouter_client import Transport
from .semantic_plan_protected_runner import projected_paid_route_probe


def _sanitise(value: Any, api_key: str) -> str:
    message = " ".join(str(value or "route probe failed").split())[:500]
    return message.replace(api_key, "[REDACTED]") if api_key else message


def _route_evidence_path(config: GenerationConfig) -> Path | None:
    root = os.environ.get("CRYPTOPULSE_SELECTOR_EVIDENCE_DIR")
    if not root:
        return None
    slug = config.model.replace("/", "__").replace(":", "_")
    return Path(root).resolve() / "route-probes" / f"{slug}.json"


def _write_route_evidence(config: GenerationConfig, payload: Mapping[str, Any]) -> None:
    path = _route_evidence_path(config)
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(dict(payload)) + b"\n")


def metered_stage0_route_probe(
    config: GenerationConfig,
    api_key: str,
    *,
    transport: Transport | None = None,
) -> Mapping[str, Any]:
    """Persist a reported probe or reserve the reviewed cap after network failure."""

    try:
        result = dict(
            projected_paid_route_probe(
                config,
                api_key,
                transport=transport,
            )
        )
    except Exception as exc:
        evidence = {
            "requested_model": config.model,
            "actual_model": None,
            "actual_provider": None,
            "estimated_cost_usd": config.max_cost_usd,
            "metering_status": "reserved-maximum",
            "probe_status": "failed",
            "failure_code": str(
                getattr(exc, "code", None) or "route_preflight_failure"
            ),
            "message": _sanitise(exc, api_key),
        }
        _write_route_evidence(config, evidence)
        return evidence

    evidence = {
        **result,
        "metering_status": "reported",
        "probe_status": "passed",
    }
    _write_route_evidence(config, evidence)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--repository-root", default=".")
    prepare.add_argument("--config", default=DEFAULT_STAGE0_CONFIG)
    prepare.add_argument("--output-dir", required=True)
    run = commands.add_parser("run")
    run.add_argument("--repository-root", default=".")
    run.add_argument("--config", default=DEFAULT_STAGE0_CONFIG)
    run.add_argument("--prepared-dir", required=True)
    run.add_argument("--output-dir", required=True)
    run.add_argument("--trusted-main-sha")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare_stage0(
                repository_root=args.repository_root,
                config_path=args.config,
                output_dir=args.output_dir,
            )
        else:
            result = execute_stage0(
                repository_root=args.repository_root,
                config_path=args.config,
                prepared_dir=args.prepared_dir,
                output_dir=args.output_dir,
                api_key=os.environ.get("OPENROUTER_API_KEY"),
                trusted_main_sha=args.trusted_main_sha,
                route_probe=metered_stage0_route_probe,
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (
        EvaluationConfigurationError,
        EvaluationIntegrityError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        print(f"low-cost candidate-selector Stage 0 failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
