"""Hostile contract tests for observed-price-history/v2-terminal."""
import copy
import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from observed_price_history import (ObservedPriceError, _classify, canonical, materialise, validate_replay)

COMMIT = "cbaac787015cce6ecf9d2f07bba4a603d3f0f4c2"


class ObservedPriceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = materialise(ROOT, COMMIT)

    def test_exact_24_hour_oracle(self):
        data = self.record
        self.assertEqual(data["window"], {"start_utc": "2026-09-11T01:00:00Z", "end_utc": "2026-09-12T00:00:00Z", "slots": 24})
        self.assertEqual(len(data["entries"]), 24)
        self.assertEqual(sum(x["state"] == "OBSERVED" for x in data["entries"]), 6)
        self.assertEqual(sum(x["state"] == "MISSING" for x in data["entries"]), 18)
        self.assertEqual(sum(v is not None for e in data["entries"] for v in e["prices_usd"].values()), 18)

    def test_deterministic_canonical_bytes(self):
        self.assertEqual(canonical(self.record), canonical(materialise(ROOT, COMMIT)))
        self.assertEqual(validate_replay(ROOT, self.record), self.record)
        without_id = {k: v for k, v in self.record.items() if k != "record_id"}
        self.assertEqual(hashlib.sha256(canonical(without_id)).hexdigest(), self.record["record_id"])

    def test_tampered_canonical_fields_never_validate(self):
        samples = [
            lambda j: j["entries"][3]["prices_usd"].update(BTC=12),
            lambda j: j["entries"].pop(),
            lambda j: j["entries"].reverse(),
            lambda j: j["repository_context"].update(tree_sha="0" * 40),
            lambda j: j["entries"][3]["candidates"][0].update(snapshot_sha256="0" * 64),
            lambda j: j["entries"][3]["candidates"][0].update(git_blob_sha="0" * 40),
            lambda j: j["entries"][3].update(state="MISSING"),
            lambda j: j["entries"][3].update(warnings=["invented"]),
        ]
        for change in samples:
            with self.subTest(change=change):
                record = copy.deepcopy(self.record)
                change(record)
                record["record_id"] = hashlib.sha256(canonical({k: v for k, v in record.items() if k != "record_id"})).hexdigest()
                with self.assertRaises(ObservedPriceError):
                    validate_replay(ROOT, record)

    def test_duplicate_hour_is_blocked(self):
        slot = "2026-09-11T04:00:00Z"
        from resolve_crypto_observation_hour_adjacency import prepare_observation_hour_replay_context
        ctx = prepare_observation_hour_replay_context(ROOT, COMMIT)
        item = ctx._population[slot][0]
        result = _classify([item, item], slot, ctx._config)
        self.assertEqual(result["state"], "AMBIGUOUS")
        self.assertTrue(all(x is None for x in result["prices_usd"].values()))

    def test_missing_hour_is_not_an_invalid_hour(self):
        row = _classify([], "2026-09-11T01:00:00Z", {})
        self.assertEqual(row["state"], "MISSING")
        self.assertEqual(row["candidates"], [])

    def test_validator_runtime_failure_is_terminal(self):
        from resolve_crypto_observation_hour_adjacency import prepare_observation_hour_replay_context
        ctx = prepare_observation_hour_replay_context(ROOT, COMMIT)
        item = ctx._population["2026-09-11T04:00:00Z"][0]
        with patch("observed_price_history.validate_observation_hour", side_effect=OSError("I/O failure")):
            with self.assertRaises(ObservedPriceError):
                _classify([item], "2026-09-11T04:00:00Z", ctx._config)

    def test_invalid_repository_authority_aborts(self):
        with self.assertRaises(ObservedPriceError):
            materialise(ROOT, "0" * 40)

    def test_unsupported_candidate_shape_rejected(self):
        for bad in (None, [], {"repository_context": {}}, {"repository_context": {"commit_sha": "0" * 40}}):
            with self.subTest(bad=bad), self.assertRaises(ObservedPriceError):
                validate_replay(ROOT, bad)


    def _valid_item(self):
        from resolve_crypto_observation_hour_adjacency import prepare_observation_hour_replay_context
        ctx = prepare_observation_hour_replay_context(ROOT, COMMIT)
        slot = "2026-09-11T04:00:00Z"
        return ctx, slot, ctx._population[slot][0]

    def test_projection_rejects_all_malformed_asset_variants(self):
        from observed_price_history import CandidateProjectionInvalid, _project
        _, _, item = self._valid_item()
        original = item[2]

        def mutate(case, payload):
            assets = payload["market"]["assets"]
            selected = next(a for a in assets if a["symbol"] == "BTC")
            if case == "boolean":
                selected["price_usd"] = True
            elif case == "zero":
                selected["price_usd"] = 0
            elif case == "negative":
                selected["price_usd"] = -1
            elif case == "nan":
                selected["price_usd"] = float("nan")
            elif case == "positive-infinity":
                selected["price_usd"] = float("inf")
            elif case == "negative-infinity":
                selected["price_usd"] = float("-inf")
            elif case == "absent":
                assets.remove(selected)
            elif case == "duplicate":
                assets.append(copy.deepcopy(selected))
            elif case == "wrong-id":
                selected["id"] = "not-bitcoin"
            elif case == "missing-price":
                selected.pop("price_usd")
            elif case == "non-object":
                assets.append(None)
            elif case == "missing-assets":
                payload["market"].pop("assets")
            elif case == "missing-market":
                payload.pop("market")

        cases = ("boolean", "zero", "negative", "nan", "positive-infinity",
                 "negative-infinity", "absent", "duplicate", "wrong-id",
                 "missing-price", "non-object", "missing-assets", "missing-market")
        for case in cases:
            with self.subTest(case=case):
                bad = copy.deepcopy(original)
                mutate(case, bad)
                with self.assertRaises(CandidateProjectionInvalid):
                    _project(bad)

    def test_expected_projection_rejection_is_whole_hour(self):
        from observed_price_history import CandidateProjectionInvalid
        ctx, slot, item = self._valid_item()
        with patch("observed_price_history._project",
                   side_effect=CandidateProjectionInvalid("bad asset")):
            entry = _classify([item], slot, ctx._config)
        self.assertEqual(entry["state"], "INVALID")
        self.assertEqual(entry["blocked_reason"], "projection-invalid")
        self.assertEqual(entry["prices_usd"], {"BTC": None, "ETH": None, "SOL": None})

    def test_unexpected_projection_faults_are_terminal(self):
        for failure in (KeyError("bug"), TypeError("bug"), ValueError("bug"),
                        OSError("filesystem"), RuntimeError("broken runtime")):
            with self.subTest(failure=type(failure).__name__):
                with patch("observed_price_history._project", side_effect=failure):
                    with self.assertRaises(ObservedPriceError) as result:
                        materialise(ROOT, COMMIT)
                self.assertIsInstance(result.exception, ObservedPriceError)

    def test_phase12_rejection_vs_execution_failure(self):
        from validate_crypto_snapshot import ValidationError
        ctx, slot, item = self._valid_item()
        # A forged, unchained ValidationError has no validator-owned source
        # rejection site and must not silently turn the hour INVALID.
        with patch("observed_price_history.validate_observation_hour",
                   side_effect=ValidationError("bad source")):
            with self.assertRaises(ObservedPriceError) as unexpected:
                materialise(ROOT, COMMIT)
        self.assertIsInstance(unexpected.exception, ObservedPriceError)

        # Genuine, bare Phase 12 source rejection remains recoverable.
        import json
        payload = copy.deepcopy(item[2])
        payload["run"].pop("observation_hour_utc")
        raw = json.dumps(payload).encode("utf-8")
        entry = _classify([(item[0], raw, payload)], slot, ctx._config)
        self.assertEqual(entry["state"], "INVALID")
        self.assertTrue(all(v is None for v in entry["prices_usd"].values()))
        try:
            raise ValidationError("wrapped I/O") from OSError("unavailable disk")
        except ValidationError as wrapped:
            with patch("observed_price_history.validate_observation_hour",
                       side_effect=wrapped):
                with self.assertRaises(ObservedPriceError) as result:
                    materialise(ROOT, COMMIT)
            self.assertIsInstance(result.exception, ObservedPriceError)
        for failure in (OSError("no disk"), RuntimeError("runtime")):
            with self.subTest(failure=type(failure).__name__):
                with patch("observed_price_history.validate_observation_hour",
                           side_effect=failure):
                    with self.assertRaises(ObservedPriceError) as result:
                        materialise(ROOT, COMMIT)
                # Replaced validator imports fail authentication before execution.
                self.assertIsInstance(result.exception, ObservedPriceError)

    def test_nested_validator_execution_failures_abort_without_invalid_hour(self):
        ctx, slot, item = self._valid_item()

        def wrapped(underlying, nested=False):
            try:
                raise underlying
            except Exception as cause:
                try:
                    raise ValidationError("inner source check") from cause
                except ValidationError as intermediate:
                    if not nested:
                        return intermediate
                    try:
                        raise ValidationError("outer source check") from intermediate
                    except ValidationError as outer:
                        return outer

        from validate_crypto_snapshot import ValidationError
        for failure in (KeyError("missing runtime key"), TypeError("validator bug"),
                        AttributeError("validator bug"), OSError("disk"),
                        RuntimeError("validator runtime"), ImportError("validator dependency")):
            for nested in (False, True):
                with self.subTest(failure=type(failure).__name__, nested=nested):
                    err = wrapped(failure, nested)
                    with patch("observed_price_history.validate_observation_hour",
                               side_effect=err):
                        with self.assertRaises(ObservedPriceError):
                            _classify([item], slot, ctx._config)
                        with self.assertRaises(ObservedPriceError):
                            materialise(ROOT, COMMIT)

    def test_forged_recognised_parser_chains_are_terminal(self):
        from validate_crypto_snapshot import ValidationError
        from json import JSONDecodeError
        ctx, slot, item = self._valid_item()

        def forged(message, cause):
            try:
                raise cause
            except Exception as exc:
                try:
                    raise ValidationError(message) from exc
                except ValidationError as final:
                    return final

        cases = (
            forged("invalid JSON", JSONDecodeError("invalid JSON", "bad", 0)),
            forged("run.generated_at_utc must be an ISO-8601 timestamp",
                   ValueError("invalid ISO format")),
            forged("wrapped runtime failure", ValueError("unexpected internal failure")),
            forged("outer validator", forged("invalid JSON",
                   JSONDecodeError("invalid JSON", "bad", 0))),
        )
        for err in cases:
            with self.subTest(error=str(err)):
                with patch("observed_price_history.validate_observation_hour",
                           side_effect=err):
                    with self.assertRaises(ObservedPriceError):
                        _classify([item], slot, ctx._config)
                    with self.assertRaises(ObservedPriceError):
                        materialise(ROOT, COMMIT)

    def test_actual_phase12_json_and_timestamp_parser_rejections_recover(self):
        import json
        ctx, slot, item = self._valid_item()
        invalid_json = _classify([(item[0], b"{", item[2])], slot, ctx._config)
        self.assertEqual(invalid_json["state"], "INVALID")
        self.assertEqual(invalid_json["blocked_reason"], "phase12-invalid")
        self.assertTrue(all(x is None for x in invalid_json["prices_usd"].values()))

        payload = copy.deepcopy(item[2])
        payload["run"]["generated_at_utc"] = "invalid-time"
        raw = json.dumps(payload).encode("utf-8")
        with patch("observed_price_history._identity_is_consistent", return_value=True):
            invalid_time = _classify([(item[0], raw, payload)], slot, ctx._config)
        self.assertEqual(invalid_time["state"], "INVALID")
        self.assertEqual(invalid_time["blocked_reason"], "phase12-invalid")
        self.assertTrue(all(x is None for x in invalid_time["prices_usd"].values()))

    def test_timezone_database_failure_is_terminal(self):
        from zoneinfo import ZoneInfoNotFoundError
        ctx, slot, item = self._valid_item()
        with patch("observed_price_history.ZoneInfo",
                   side_effect=ZoneInfoNotFoundError("tzdb unavailable")):
            with self.assertRaises(ZoneInfoNotFoundError):
                _classify([item], slot, ctx._config)
            with self.assertRaises(ObservedPriceError) as result:
                materialise(ROOT, COMMIT)
        self.assertIsInstance(result.exception.__cause__, ZoneInfoNotFoundError)

    def test_proven_identity_and_timestamp_error_recover(self):
        ctx, slot, item = self._valid_item()
        bad_path = ("data/crypto/hourly/2026/09/11/"
                    "wrong_name_source_snapshot.json", item[1], item[2])
        self.assertEqual(_classify([bad_path], slot, ctx._config)["state"], "INVALID")
        payload = copy.deepcopy(item[2])
        payload["run"]["generated_at_utc"] = "not a timestamp"
        invalid_time = (item[0], item[1], payload)
        self.assertEqual(_classify([invalid_time], slot, ctx._config)["state"], "INVALID")

    def test_latest_invalid_and_ambiguous_hour_never_shift_anchor(self):
        from resolve_crypto_observation_hour_adjacency import prepare_observation_hour_replay_context
        latest = "2026-09-12T01:00:00Z"
        for candidates, state in ((1, "INVALID"), (2, "AMBIGUOUS")):
            with self.subTest(state=state):
                ctx = prepare_observation_hour_replay_context(ROOT, COMMIT)
                item = ctx._population["2026-09-11T04:00:00Z"][0]
                ctx._population[latest] = [item] * candidates
                with patch("observed_price_history.prepare_observation_hour_replay_context",
                           return_value=ctx):
                    record = materialise(ROOT, COMMIT)
                self.assertEqual(record["window"]["end_utc"], latest)
                self.assertEqual(record["window"]["start_utc"], "2026-09-11T02:00:00Z")
                self.assertEqual(len(record["entries"]), 24)
                self.assertEqual(record["entries"][-1]["state"], state)
                self.assertTrue(all(v is None for v in record["entries"][-1]["prices_usd"].values()))

    def test_unorderable_and_malformed_asserted_population_abort(self):
        import json
        from resolve_crypto_observation_hour_adjacency import (
            ObservationHourPopulationError, _load_observation_hour_population_exact,
        )
        _, _, item = self._valid_item()
        path = item[0]
        payload = copy.deepcopy(item[2])
        payload["run"]["observation_hour_utc"] = "bad-hour"
        for raw in (json.dumps(payload).encode("utf-8"),
                    b'{"run":{"observation_hour_utc":"2026-09-11T04:00:00Z"'):
            with self.subTest(raw=raw[:48]):
                with patch("resolve_crypto_observation_hour_adjacency._candidate_paths",
                           return_value=[path]), patch(
                    "resolve_crypto_observation_hour_adjacency._bytes_at_commit",
                    return_value=raw
                ):
                    with self.assertRaises(ObservationHourPopulationError):
                        _load_observation_hour_population_exact(ROOT, COMMIT)

    def test_tampering_validation_refs_and_generated_identity_is_rejected(self):
        for update in (
            lambda r: r["repository_context"]["validation_refs"]["config"].update(git_blob_sha="0"*40),
            lambda r: r["repository_context"]["validation_refs"]["snapshot_validator"].update(path="evil.py"),
            lambda r: r["entries"][3]["candidates"][0].update(generated_at_utc="forged"),
            lambda r: r["entries"][3]["candidates"][0].update(quality_status="valid-degraded"),
            lambda r: r["entries"][3].update(blocked_reason="forged"),
            lambda r: r["entries"][3].update(slot_utc="2026-01-01T00:00:00Z"),
        ):
            with self.subTest(update=update):
                candidate = copy.deepcopy(self.record)
                update(candidate)
                without_id = {k: v for k, v in candidate.items() if k != "record_id"}
                candidate["record_id"] = hashlib.sha256(canonical(without_id)).hexdigest()
                with self.assertRaises(ObservedPriceError):
                    validate_replay(ROOT, candidate)

    def test_whole_window_is_consecutive_and_provenance_total(self):
        from datetime import datetime, timedelta
        rows = self.record["entries"]
        self.assertEqual(len(rows), 24)
        initial = datetime.fromisoformat(rows[0]["slot_utc"].replace("Z", "+00:00"))
        self.assertEqual(
            [r["slot_utc"] for r in rows],
            [(initial + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00:00Z")
             for i in range(24)]
        )
        for row in rows:
            if row["state"] == "MISSING":
                self.assertEqual(row["candidates"], [])
            for source in row["candidates"]:
                self.assertEqual(set(source),
                                 {"path", "git_blob_sha", "snapshot_sha256",
                                  "observation_hour_utc", "generated_at_utc",
                                  "quality_status"})
                self.assertEqual(len(source["git_blob_sha"]), 40)
                self.assertEqual(len(source["snapshot_sha256"]), 64)
            if row["state"] not in ("OBSERVED", "OBSERVED_DEGRADED"):
                self.assertTrue(all(v is None for v in row["prices_usd"].values()))


    def test_pinned_rejection_authority_rejects_mutable_source_and_linecache(self):
        import linecache
        import tempfile
        from unittest.mock import patch
        from observed_price_history import _authenticated_validator_modules, _explicit_phase12_source_rejection
        import validate_crypto_snapshot as snapshot_module
        _authenticated_validator_modules()
        try:
            snapshot_module.require_mapping(None, "run")
        except snapshot_module.ValidationError as err:
            genuine = err
        self.assertTrue(_explicit_phase12_source_rejection(genuine))
        with patch.object(linecache, "getline", return_value="raise ValidationError('forged')"):
            self.assertTrue(_explicit_phase12_source_rejection(genuine))
            try:
                raise snapshot_module.ValidationError("forged")
            except snapshot_module.ValidationError as forged:
                self.assertFalse(_explicit_phase12_source_rejection(forged))
        original = Path(snapshot_module.__file__).read_bytes()
        with patch.object(Path, "read_bytes", autospec=True,
                          side_effect=lambda path: original + b"\n# altered" if Path(path).resolve() == Path(snapshot_module.__file__).resolve() else Path.open(path, "rb").read()):
            with self.assertRaises(ObservedPriceError):
                _authenticated_validator_modules()

    def test_unknown_validator_execution_site_is_not_recoverable(self):
        from observed_price_history import _explicit_phase12_source_rejection
        import validate_crypto_snapshot as validator
        from unittest.mock import patch
        def fabricated_rejection(_value, _path):
            raise validator.ValidationError("fake schema failure")
        with patch.object(validator, "require_mapping", fabricated_rejection):
            from observed_price_history import _authenticated_validator_modules
            with self.assertRaises(ObservedPriceError):
                _authenticated_validator_modules()
            with self.assertRaises(validator.ValidationError) as captured:
                validator.require_mapping(None, "run")
            with self.assertRaises(ObservedPriceError):
                _explicit_phase12_source_rejection(captured.exception)


    def test_actual_invocation_targets_and_nested_helpers_cannot_fabricate_success(self):
        import validate_crypto_snapshot as snapshot_module
        import validate_crypto_observation_hour as observation_module
        ctx, slot, item = self._valid_item()
        passing_hour = {"observation_hour_utc": slot}
        passing_quality = {"status": "valid-ok", "non_blocking_warnings": []}
        attacks = (
            ("direct observation", "observed_price_history.validate_observation_hour", passing_hour),
            ("direct snapshot", "observed_price_history.validate_snapshot", passing_quality),
            ("nested snapshot", "validate_crypto_observation_hour.validate_snapshot", passing_quality),
            ("nested parser", "validate_crypto_observation_hour.parse_iso_timestamp", object()),
            ("snapshot helper", "validate_crypto_snapshot.require_mapping", {}),
            ("snapshot quality", "validate_crypto_snapshot.validate_quality", passing_quality),
        )
        for name, path, fake_result in attacks:
            with self.subTest(name=name), patch(path, return_value=fake_result):
                with self.assertRaises(ObservedPriceError):
                    _classify([item], slot, ctx._config)
                with self.assertRaises(ObservedPriceError):
                    materialise(ROOT, COMMIT)
        # No call-target injection may leave the original imports altered.
        from observed_price_history import _authenticated_validator_modules
        _authenticated_validator_modules()
        self.assertIs(snapshot_module.validate_snapshot, observation_module.validate_snapshot)

    def test_synthetic_json_decode_and_timestamp_parser_chains_remain_terminal(self):
        import json
        from json import JSONDecodeError
        import validate_crypto_snapshot as snapshot_module
        from observed_price_history import _authenticated_validator_modules
        ctx, slot, item = self._valid_item()
        synthetic_decode = JSONDecodeError("forged parser rejection", "bad", 0)
        with patch("json.loads", side_effect=synthetic_decode):
            with self.assertRaises(ObservedPriceError):
                _classify([item], slot, ctx._config)
            with self.assertRaises(ObservedPriceError):
                materialise(ROOT, COMMIT)
        with patch.object(snapshot_module, "parse_iso_timestamp", side_effect=ValueError("ISO-8601")):
            with self.assertRaises(ObservedPriceError):
                _classify([item], slot, ctx._config)
        # A real malformed committed candidate remains a recoverable source error.
        bad = copy.deepcopy(item[2])
        bad["run"]["generated_at_utc"] = "not-ISO"
        with patch("observed_price_history._identity_is_consistent", return_value=True):
            classified = _classify([(item[0], json.dumps(bad).encode(), bad)], slot, ctx._config)
        self.assertEqual(classified["state"], "INVALID")
        self.assertEqual(classified["blocked_reason"], "phase12-invalid")
        _authenticated_validator_modules()

    def test_mutable_validator_policy_cannot_fabricate_success(self):
        import validate_crypto_snapshot as validator
        ctx, slot, item = self._valid_item()
        with patch.object(validator, "REQUIRED_RUN_KEYS", set()):
            with self.assertRaises(ObservedPriceError):
                _classify([item], slot, ctx._config)
        with patch.object(validator, "VALID_SOURCE_STATUSES", {"ok", "broken"}):
            with self.assertRaises(ObservedPriceError):
                materialise(ROOT, COMMIT)

    def test_compiled_class_body_is_not_validator_function(self):
        import validate_crypto_snapshot as snapshot_module
        from observed_price_history import _authenticated_validator_modules
        sources = _authenticated_validator_modules()
        self.assertIsInstance(snapshot_module.ValidationError, type)
        self.assertIs(sources["validate_crypto_snapshot"][0], snapshot_module)


if __name__ == "__main__":
    unittest.main()
