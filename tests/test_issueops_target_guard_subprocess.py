from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from issueops_dispatch import target_guard as guard
from tests.test_issueops_target_guard import (
    DISPATCHER_RUN_ID,
    EXECUTION_REF,
    RUN_ID,
    SHA,
    dispatcher_run,
    record_for,
    verified_payload,
)


class _BundleResponse:
    def __init__(self, payload: bytes) -> None:
        self.status = 200
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class VerifierSubprocessBoundaryTests(unittest.TestCase):
    def _fake_gh(
        self,
        root: Path,
        *,
        stdout: bytes,
        stderr: bytes = b"",
        returncode: int = 0,
    ) -> Path:
        binary = root / "fake-gh"
        stdout_b64 = base64.b64encode(stdout).decode("ascii")
        stderr_b64 = base64.b64encode(stderr).decode("ascii")
        binary.write_text(
            "#!/usr/bin/env python3\n"
            "import base64\n"
            "import sys\n"
            f"sys.stdout.buffer.write(base64.b64decode({stdout_b64!r}))\n"
            f"sys.stderr.buffer.write(base64.b64decode({stderr_b64!r}))\n"
            f"raise SystemExit({returncode})\n",
            encoding="utf-8",
        )
        binary.chmod(0o755)
        return binary

    def _run(
        self,
        root: Path,
        *,
        stdout: bytes,
        stderr: bytes = b"",
        returncode: int = 0,
    ):
        return guard.run_gh_verify(
            gh_binary=self._fake_gh(
                root,
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
            subject_path=root / "dispatch-subject.json",
            bundle_path=root / "bundle.json",
            source_sha=SHA,
            token="unused",
        )

    def test_valid_stdout_with_non_utf8_stderr_reaches_semantic_verification(self) -> None:
        record = record_for(b"workflow")
        payload = verified_payload(record)
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(
                Path(tmp),
                stdout=json.dumps(payload).encode("utf-8"),
                stderr=b"diagnostic: \xc3(\n",
            )

        resolution = guard.build_resolution(
            record=record,
            source_sha=SHA,
            execution_ref=EXECUTION_REF,
        )
        dispatcher_run_id = guard.verify_gh_result(
            result,
            resolution=resolution,
            target_run_id=RUN_ID,
            run_lookup=lambda _: dispatcher_run(),
        )
        self.assertEqual(dispatcher_run_id, DISPATCHER_RUN_ID)

    def test_nonzero_exit_with_malformed_output_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(
                Path(tmp),
                stdout=b"\xc3(",
                stderr=b"\xff\xfe",
                returncode=1,
            )
        self.assertIsNone(result)

    def test_success_with_non_utf8_stdout_fails_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(guard.GuardError, "non-UTF-8"):
                self._run(Path(tmp), stdout=b"\xc3(")

    def test_success_with_malformed_json_fails_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(guard.GuardError, "malformed JSON"):
                self._run(Path(tmp), stdout=b"not-json")

    def test_success_with_valid_json_is_returned(self) -> None:
        payload = [{"verificationResult": {"fixture": True}}]
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(
                Path(tmp),
                stdout=json.dumps(payload).encode("utf-8"),
            )
        self.assertEqual(result, payload)

    def test_attestation_bundle_download_preserves_raw_bytes(self) -> None:
        payload = b"\x00\xc3(\xff\n"
        response = _BundleResponse(payload)
        api = guard.GitHubReadAPI(guard.REPOSITORY, "unused")
        with patch.object(guard.urllib.request, "urlopen", return_value=response):
            result = api.fetch_bundle("https://example.invalid/bundle.json")
        self.assertEqual(result, payload)


if __name__ == "__main__":
    unittest.main()
