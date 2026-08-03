from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from llm_analysis.candidate_selector_stage0 import (
    STAGE0_PREPARED_MANIFEST,
    execute_stage0,
    prepare_stage0,
)
from tests.test_candidate_selector_stage0 import (
    CONFIG,
    ROOT,
    CandidateSelectorStage0Tests,
    _SelectorTransport,
)


class CandidateSelectorStage0ClassificationTests(unittest.TestCase):
    def _prepare(self, directory: Path) -> tuple[Path, str]:
        prepared = directory / "prepared"
        prepare_stage0(
            repository_root=ROOT,
            config_path=CONFIG,
            output_dir=prepared,
        )
        manifest = json.loads(
            (prepared / STAGE0_PREPARED_MANIFEST).read_text(encoding="utf-8")
        )
        baseline = json.loads(
            (prepared / manifest["paths"]["baseline_selection"]).read_text(
                encoding="utf-8"
            )
        )
        return prepared, baseline["selected_candidate_ids"][0]

    @staticmethod
    def _catalogue() -> dict[str, Any]:
        return CandidateSelectorStage0Tests._catalogue()

    def test_schema_incompatible_is_distinct_from_route_ineligible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepared, selected_id = self._prepare(root)
            transport = _SelectorTransport(selected_id)

            def schema_failure(config: Any, api_key: str, *, transport: Any = None) -> dict[str, Any]:
                del api_key, transport
                return {
                    "requested_model": config.model,
                    "actual_model": None,
                    "actual_provider": None,
                    "estimated_cost_usd": config.max_cost_usd,
                    "metering_status": "reserved-maximum",
                    "probe_status": "failed",
                    "failure_code": "provider_error",
                    "message": "The selected endpoint does not support response_format json_schema",
                }

            summary = execute_stage0(
                repository_root=ROOT,
                config_path=CONFIG,
                prepared_dir=prepared,
                output_dir=root / "output",
                api_key="test-secret",
                catalogue_loader=self._catalogue,
                route_probe=schema_failure,
                transport_factory=lambda: transport,
            )
            self.assertEqual(
                [row["classification"] for row in summary["models"]],
                ["schema-incompatible"] * 3,
            )
            self.assertEqual(summary["completed_selector_generations"], 0)

    def test_route_identity_mismatch_is_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepared, selected_id = self._prepare(root)
            transport = _SelectorTransport(selected_id)

            def wrong_identity(config: Any, api_key: str, *, transport: Any = None) -> dict[str, Any]:
                del api_key, transport
                return {
                    "requested_model": config.model,
                    "actual_model": config.model,
                    "actual_provider": "Unexpected Provider",
                    "generation_id": "wrong-provider",
                    "estimated_cost_usd": 0.0001,
                    "metering_status": "reported",
                    "probe_status": "passed",
                }

            summary = execute_stage0(
                repository_root=ROOT,
                config_path=CONFIG,
                prepared_dir=prepared,
                output_dir=root / "output",
                api_key="test-secret",
                catalogue_loader=self._catalogue,
                route_probe=wrong_identity,
                transport_factory=lambda: transport,
            )
            self.assertEqual(
                [row["classification"] for row in summary["models"]],
                ["identity-failure"] * 3,
            )
            self.assertEqual(summary["completed_selector_generations"], 0)

    def test_catalogue_price_failure_is_cost_ineligible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepared, selected_id = self._prepare(root)
            transport = _SelectorTransport(selected_id)
            catalogue = copy.deepcopy(self._catalogue())
            for row in catalogue["data"]:
                row["pricing"]["prompt"] = "0.00001"

            summary = execute_stage0(
                repository_root=ROOT,
                config_path=CONFIG,
                prepared_dir=prepared,
                output_dir=root / "output",
                api_key="test-secret",
                catalogue_loader=lambda: catalogue,
                route_probe=CandidateSelectorStage0Tests._route_probe,
                transport_factory=lambda: transport,
            )
            self.assertEqual(
                [row["classification"] for row in summary["models"]],
                ["cost-ineligible"] * 3,
            )
            self.assertEqual(summary["completed_paid_calls"], 0)
            self.assertEqual(transport.calls, [])

    def test_incomplete_route_evidence_is_inconclusive_infrastructure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepared, selected_id = self._prepare(root)
            transport = _SelectorTransport(selected_id)

            def incomplete(config: Any, api_key: str, *, transport: Any = None) -> dict[str, Any]:
                del api_key, transport
                return {
                    "requested_model": config.model,
                    "actual_model": None,
                    "actual_provider": None,
                    "estimated_cost_usd": config.max_cost_usd,
                    "metering_status": "reserved-maximum",
                    "probe_status": "failed",
                    "failure_code": "route_preflight_failure",
                    "message": "The route response did not contain trustworthy usage metadata",
                }

            summary = execute_stage0(
                repository_root=ROOT,
                config_path=CONFIG,
                prepared_dir=prepared,
                output_dir=root / "output",
                api_key="test-secret",
                catalogue_loader=self._catalogue,
                route_probe=incomplete,
                transport_factory=lambda: transport,
            )
            self.assertEqual(
                [row["classification"] for row in summary["models"]],
                ["inconclusive-infrastructure"] * 3,
            )
            self.assertEqual(summary["completed_route_probes"], 3)
            self.assertEqual(summary["completed_selector_generations"], 0)
            self.assertAlmostEqual(summary["observed_total_cost_usd"], 0.06)


if __name__ == "__main__":
    unittest.main()
