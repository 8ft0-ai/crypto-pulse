from __future__ import annotations

import copy
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from crypto_observation_hour_series import (  # noqa: E402
    build_observation_hour_series,
    canonical_json_bytes,
    series_id_for_record,
    validate_observation_hour_series,
)
from phase15_public_temporal_evidence import (  # noqa: E402
    build_public_temporal_evidence,
    canonical_public_evidence_bytes,
)
from phase18_multi_asset_temporal_evidence import (  # noqa: E402
    PHASE18_CONTRACT_VERSION,
    PUBLIC_SERIES_KEYS,
    Phase18MultiAssetTemporalEvidenceError,
    build_multi_asset_temporal_evidence,
    bundle_id_for_record,
    canonical_bundle_bytes,
    validate_multi_asset_temporal_evidence,
)
from test_phase15_public_temporal_evidence_proof_corpus import (  # noqa: E402
    CORPUS_PATH,
    Phase15PublicTemporalEvidenceProofTests,
)


class Phase18MultiAssetTemporalEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.seed_helper = Phase15PublicTemporalEvidenceProofTests(
            "test_corpus_contract_is_closed"
        )
        cls.seed_helper.corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))

    def _seed(self, case_id: str):
        return self.seed_helper._seed(case_id)

    def _bundle(self, case_id: str = "deterministic-max-hour"):
        temporary, repository, commit = self._seed(case_id)
        bundle = build_multi_asset_temporal_evidence(repository, commit)
        self.assertIsNotNone(bundle)
        assert bundle is not None
        return temporary, repository, commit, bundle

    def _phase13_bundle_for_window(
        self,
        repository: Path,
        commit: str,
        start_utc: str,
        end_utc: str,
    ):
        window = {"start_utc": start_utc, "end_utc": end_utc}
        members = []
        for series_key in PUBLIC_SERIES_KEYS:
            member = build_observation_hour_series(
                repository,
                commit,
                "metric",
                series_key,
                start_utc,
                end_utc,
            )
            self.assertIs(
                validate_observation_hour_series(repository, member),
                member,
            )
            self.assertEqual(member["window"], window)
            members.append(member)

        context = members[0]["repository_context"]
        self.assertEqual(context["commit_sha"], commit)
        self.assertTrue(
            all(member["repository_context"] == context for member in members)
        )

        bundle = {
            "contract": PHASE18_CONTRACT_VERSION,
            "repository_context": copy.deepcopy(context),
            "window": copy.deepcopy(window),
            "series": members,
            "bundle_id": "",
        }
        bundle["bundle_id"] = bundle_id_for_record(bundle)
        return bundle

    def test_valid_bundle_builds_validates_and_matches_phase15_btc(self) -> None:
        temporary, repository, commit, bundle = self._bundle()
        try:
            self.assertEqual(bundle["contract"], PHASE18_CONTRACT_VERSION)
            self.assertEqual(
                [member["series_key"] for member in bundle["series"]],
                list(PUBLIC_SERIES_KEYS),
            )
            self.assertTrue(all(member["series_kind"] == "metric" for member in bundle["series"]))
            self.assertTrue(all(len(member["entries"]) == 24 for member in bundle["series"]))
            self.assertTrue(
                all(member["window"] == bundle["window"] for member in bundle["series"])
            )
            self.assertTrue(
                all(
                    member["repository_context"] == bundle["repository_context"]
                    for member in bundle["series"]
                )
            )
            self.assertEqual(bundle["repository_context"]["commit_sha"], commit)
            btc = build_public_temporal_evidence(repository, commit)
            assert btc is not None
            self.assertEqual(
                canonical_json_bytes(bundle["series"][0]),
                canonical_public_evidence_bytes(btc),
            )
            self.assertIs(validate_multi_asset_temporal_evidence(repository, bundle), bundle)
        finally:
            temporary.cleanup()

    def test_values_are_retained_independently_for_all_three_assets(self) -> None:
        temporary, _, _, bundle = self._bundle()
        try:
            latest_values = {
                member["series_key"]: [
                    entry["value"]["datum"]
                    for entry in member["entries"]
                    if entry["value"] is not None
                ]
                for member in bundle["series"]
            }
            self.assertEqual(set(latest_values), set(PUBLIC_SERIES_KEYS))
            self.assertTrue(all(values for values in latest_values.values()))
            self.assertNotEqual(latest_values["BTC.price_usd"], latest_values["ETH.price_usd"])
            self.assertNotEqual(latest_values["ETH.price_usd"], latest_values["SOL.price_usd"])
        finally:
            temporary.cleanup()

    def test_internal_gap_is_preserved_independently_for_each_asset(self) -> None:
        temporary, _, _, bundle = self._bundle("internal-gap")
        try:
            for member in bundle["series"]:
                gap = next(
                    entry
                    for entry in member["entries"]
                    if entry["slot_utc"] == "2026-07-08T05:00:00Z"
                )
                self.assertIsNone(gap["value"])
                self.assertEqual(gap["gap"]["reason"], "phase13-current-missing")
        finally:
            temporary.cleanup()

    def test_degraded_evidence_is_retained_not_normalised(self) -> None:
        temporary, _, _, bundle = self._bundle("degraded-evidence")
        try:
            for member in bundle["series"]:
                latest = member["entries"][-1]
                self.assertIsNotNone(latest["value"])
                self.assertEqual(
                    latest["value"]["comparison"]["current"]["quality_status"],
                    "valid-degraded",
                )
        finally:
            temporary.cleanup()

    def test_independent_materialisations_are_byte_identical(self) -> None:
        left_tmp, _, left_commit, left = self._bundle()
        right_tmp, _, right_commit, right = self._bundle()
        try:
            self.assertEqual(left_commit, right_commit)
            self.assertEqual(canonical_bundle_bytes(left), canonical_bundle_bytes(right))
            self.assertEqual(left["bundle_id"], right["bundle_id"])
            self.assertEqual(left["bundle_id"], bundle_id_for_record(left))
        finally:
            left_tmp.cleanup()
            right_tmp.cleanup()

    def test_zero_participation_yields_no_bundle(self) -> None:
        temporary, repository, commit = self._seed("zero-population")
        try:
            self.assertIsNone(build_multi_asset_temporal_evidence(repository, commit))
        finally:
            temporary.cleanup()

    def test_member_value_and_evidence_tamper_are_rejected(self) -> None:
        temporary, repository, _, bundle = self._bundle()
        try:
            for mutation in ("datum", "evidence"):
                with self.subTest(mutation=mutation):
                    tampered = copy.deepcopy(bundle)
                    target = next(
                        entry for entry in tampered["series"][1]["entries"]
                        if entry["value"] is not None
                    )
                    if mutation == "datum":
                        target["value"]["datum"] = 999999999
                    else:
                        target["value"]["evidence"]["current"]["value"] = 999999999
                    tampered["series"][1]["series_id"] = series_id_for_record(
                        tampered["series"][1]
                    )
                    tampered["bundle_id"] = bundle_id_for_record(tampered)
                    with self.assertRaisesRegex(
                        Phase18MultiAssetTemporalEvidenceError,
                        "immutable replay",
                    ):
                        validate_multi_asset_temporal_evidence(repository, tampered)
        finally:
            temporary.cleanup()

    def test_nested_series_id_and_bundle_id_tamper_are_rejected(self) -> None:
        temporary, repository, _, bundle = self._bundle()
        try:
            nested = copy.deepcopy(bundle)
            nested["series"][2]["series_id"] = "0" * 64
            nested["bundle_id"] = bundle_id_for_record(nested)
            with self.assertRaises(Phase18MultiAssetTemporalEvidenceError):
                validate_multi_asset_temporal_evidence(repository, nested)

            outer = copy.deepcopy(bundle)
            outer["bundle_id"] = "0" * 64
            with self.assertRaisesRegex(
                Phase18MultiAssetTemporalEvidenceError, "bundle_id"
            ):
                validate_multi_asset_temporal_evidence(repository, outer)
        finally:
            temporary.cleanup()

    def test_unknown_additional_and_reordered_series_are_rejected(self) -> None:
        temporary, repository, _, bundle = self._bundle()
        try:
            additional = copy.deepcopy(bundle)
            additional["series"].append(copy.deepcopy(additional["series"][0]))
            additional["bundle_id"] = bundle_id_for_record(additional)
            with self.assertRaisesRegex(
                Phase18MultiAssetTemporalEvidenceError, "exactly BTC, ETH and SOL"
            ):
                validate_multi_asset_temporal_evidence(repository, additional)

            reordered = copy.deepcopy(bundle)
            reordered["series"][0], reordered["series"][1] = (
                reordered["series"][1],
                reordered["series"][0],
            )
            reordered["bundle_id"] = bundle_id_for_record(reordered)
            with self.assertRaisesRegex(
                Phase18MultiAssetTemporalEvidenceError, "identity/order"
            ):
                validate_multi_asset_temporal_evidence(repository, reordered)

            unknown = copy.deepcopy(bundle)
            unknown["series"][2]["series_key"] = "DOGE.price_usd"
            unknown["bundle_id"] = bundle_id_for_record(unknown)
            with self.assertRaisesRegex(
                Phase18MultiAssetTemporalEvidenceError, "identity/order"
            ):
                validate_multi_asset_temporal_evidence(repository, unknown)
        finally:
            temporary.cleanup()

    def test_window_context_and_alternative_anchor_substitution_are_rejected(self) -> None:
        temporary, repository, commit, bundle = self._bundle()
        try:
            window_mismatch = copy.deepcopy(bundle)
            window_mismatch["series"][1]["window"] = copy.deepcopy(
                window_mismatch["series"][1]["window"]
            )
            window_mismatch["series"][1]["window"]["end_utc"] = "2026-07-08T07:00:00Z"
            window_mismatch["bundle_id"] = bundle_id_for_record(window_mismatch)
            with self.assertRaisesRegex(
                Phase18MultiAssetTemporalEvidenceError, "window mismatch"
            ):
                validate_multi_asset_temporal_evidence(repository, window_mismatch)

            context_mismatch = copy.deepcopy(bundle)
            context_mismatch["series"][2]["repository_context"] = copy.deepcopy(
                context_mismatch["series"][2]["repository_context"]
            )
            context_mismatch["series"][2]["repository_context"]["commit_sha"] = "0" * 40
            context_mismatch["bundle_id"] = bundle_id_for_record(context_mismatch)
            with self.assertRaisesRegex(
                Phase18MultiAssetTemporalEvidenceError, "repository context mismatch"
            ):
                validate_multi_asset_temporal_evidence(repository, context_mismatch)

            alternate = self._phase13_bundle_for_window(
                repository,
                commit,
                "2026-07-07T08:00:00Z",
                "2026-07-08T07:00:00Z",
            )
            self.assertNotEqual(alternate["window"], bundle["window"])
            with self.assertRaisesRegex(
                Phase18MultiAssetTemporalEvidenceError,
                "Phase 15 BTC canonical compatibility mismatch",
            ):
                validate_multi_asset_temporal_evidence(repository, alternate)
        finally:
            temporary.cleanup()

    def test_non_24_slot_and_non_json_native_or_nonfinite_values_are_rejected(self) -> None:
        temporary, repository, _, bundle = self._bundle()
        try:
            short = copy.deepcopy(bundle)
            short["window"]["start_utc"] = short["window"]["end_utc"]
            short["bundle_id"] = bundle_id_for_record(short)
            with self.assertRaisesRegex(
                Phase18MultiAssetTemporalEvidenceError, "24 canonical slots"
            ):
                validate_multi_asset_temporal_evidence(repository, short)

            non_native = copy.deepcopy(bundle)
            non_native["series"] = tuple(non_native["series"])
            with self.assertRaisesRegex(
                Phase18MultiAssetTemporalEvidenceError, "non-JSON-native"
            ):
                validate_multi_asset_temporal_evidence(repository, non_native)

            nonfinite = copy.deepcopy(bundle)
            nonfinite["repository_context"]["bad"] = math.nan
            with self.assertRaisesRegex(
                Phase18MultiAssetTemporalEvidenceError, "non-finite"
            ):
                validate_multi_asset_temporal_evidence(repository, nonfinite)
        finally:
            temporary.cleanup()

    def test_phase15_btc_mismatch_is_rejected_after_phase13_replay_succeeds(self) -> None:
        temporary, repository, commit, selected = self._bundle()
        try:
            alternate = self._phase13_bundle_for_window(
                repository,
                commit,
                "2026-07-07T08:00:00Z",
                "2026-07-08T07:00:00Z",
            )
            self.assertNotEqual(alternate["window"], selected["window"])
            self.assertNotEqual(alternate["bundle_id"], selected["bundle_id"])

            phase15_btc = build_public_temporal_evidence(repository, commit)
            assert phase15_btc is not None
            self.assertNotEqual(
                canonical_json_bytes(alternate["series"][0]),
                canonical_public_evidence_bytes(phase15_btc),
            )

            with self.assertRaisesRegex(
                Phase18MultiAssetTemporalEvidenceError,
                "Phase 15 BTC canonical compatibility mismatch",
            ):
                validate_multi_asset_temporal_evidence(repository, alternate)
        finally:
            temporary.cleanup()

    def test_bundle_surface_adds_no_derived_market_fields(self) -> None:
        temporary, _, _, bundle = self._bundle()
        try:
            self.assertEqual(
                set(bundle),
                {"contract", "repository_context", "window", "series", "bundle_id"},
            )
            forbidden = {
                "return",
                "ranking",
                "rebased",
                "normalised",
                "normalized",
                "aggregate",
                "trend",
            }
            self.assertTrue(forbidden.isdisjoint(bundle.keys()))
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
