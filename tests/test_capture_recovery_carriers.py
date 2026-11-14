"""Closed checks for one immutable pre-authorised source-exclusion pin."""
from __future__ import annotations

import hashlib
import json
import unittest
from unittest.mock import patch, Mock

from scripts import capture_recovery_carriers as cap

REPO = "8ft0-ai/crypto-pulse"


def census(*ids):
    return {"runs": [{"run_id": i} for i in ids]}


def comment(body, *, author="8ft0-ai", issue=523, number=cap.PINNED_COMMENT):
    return {
        "id": number,
        "user": {"login": author},
        "issue_url": f"https://api.github.com/repos/{REPO}/issues/{issue}",
        "body": body,
    }


def body():
    return json.dumps({
        "contract": "trusted-main-source-evidence-recovery-decision/v1",
        "disposition": "exclude-from-accumulation",
        "blocker_fingerprint": cap.PINNED_FINGERPRINT,
        "input_identities": [{"run_id": cap.PINNED_SOURCE_RUN}],
    }, sort_keys=True, separators=(",", ":"))


class PinnedRecoveryTests(unittest.TestCase):
    def test_scheduled_selects_only_owner_pinned_historical_run(self):
        self.assertEqual(cap.ids_for_capture("schedule", "", census(
            100, cap.PINNED_SOURCE_RUN, 200)), [cap.PINNED_COMMENT])
        self.assertEqual(cap.ids_for_capture("schedule", "", census(100, 200)), [])

    def test_scheduled_never_discovers_new_or_custom_exceptions(self):
        for raw in ("2", str(cap.PINNED_COMMENT), "   ", "123,456"):
            with self.subTest(raw=raw), self.assertRaises(cap.RecoveryCaptureError):
                cap.ids_for_capture("schedule", raw, census(cap.PINNED_SOURCE_RUN))
        self.assertEqual(cap.ids_for_capture("schedule", "", census(12345)), [])

    def test_census_is_complete_and_unambiguous(self):
        for invalid in ({}, {"runs": None}, {"runs": [42]},
                        census(cap.PINNED_SOURCE_RUN, cap.PINNED_SOURCE_RUN)):
            with self.subTest(invalid=invalid), self.assertRaises(cap.RecoveryCaptureError):
                cap.ids_for_capture("schedule", "", invalid)

    def test_manual_recovery_remains_explicit_and_checked(self):
        self.assertEqual(cap.ids_for_capture("workflow_dispatch", "13,14\n15", census()), [13, 14, 15])
        self.assertEqual(cap.ids_for_capture("workflow_dispatch", "", census()), [])
        for raw in ("0", "-2", "x", "1,1"):
            with self.subTest(raw=raw), self.assertRaises(cap.RecoveryCaptureError):
                cap.ids_for_capture("workflow_dispatch", raw, census())

    def test_invalid_event_fails_closed(self):
        with self.assertRaises(cap.RecoveryCaptureError):
            cap.ids_for_capture("push", "", census(cap.PINNED_SOURCE_RUN))

    def test_correct_owner_binding_is_encoded_and_hashed(self):
        raw = body()
        with patch.object(cap, "PINNED_BODY_SHA256", hashlib.sha256(raw.encode()).hexdigest()):
            row = cap.capture_comment(comment(raw), cap.PINNED_COMMENT, "schedule", REPO)
        self.assertEqual(row["comment_id"], cap.PINNED_COMMENT)
        self.assertEqual(row["issue_number"], 523)
        self.assertEqual(row["author_login"], "8ft0-ai")
        self.assertEqual(row["body_sha256"], hashlib.sha256(raw.encode()).hexdigest())

    def test_modified_owner_comment_or_wrong_identity_stops(self):
        raw = body()
        good_hash = hashlib.sha256(raw.encode()).hexdigest()
        variants = [
            comment(raw + " "),
            comment(raw, author="impostor"),
            comment(raw, issue=524),
            comment(raw, number=cap.PINNED_COMMENT + 1),
            comment(raw.replace(cap.PINNED_FINGERPRINT, "0"*64)),
        ]
        with patch.object(cap, "PINNED_BODY_SHA256", good_hash):
            for row in variants:
                with self.subTest(row=row), self.assertRaises(cap.RecoveryCaptureError):
                    cap.capture_comment(row, cap.PINNED_COMMENT, "schedule", REPO)

    def test_pinned_content_requires_exact_source_run_even_with_matching_hash(self):
        wrong = json.dumps({
            "contract": "trusted-main-source-evidence-recovery-decision/v1",
            "disposition": "exclude-from-accumulation",
            "blocker_fingerprint": cap.PINNED_FINGERPRINT,
            "input_identities": [{"run_id": 999}],
        })
        with patch.object(cap, "PINNED_BODY_SHA256", hashlib.sha256(wrong.encode()).hexdigest()):
            with self.assertRaises(cap.RecoveryCaptureError):
                cap.capture_comment(comment(wrong), cap.PINNED_COMMENT, "schedule", REPO)

    def test_scheduled_absent_requires_no_network_access(self):
        with patch.object(cap.subprocess, "run") as run:
            self.assertEqual(cap.capture(REPO, "schedule", "", census(123)), [])
            run.assert_not_called()

    def test_scheduled_fetches_only_the_preapproved_comment(self):
        raw = body()
        response = Mock(stdout=json.dumps(comment(raw)))
        with patch.object(cap, "PINNED_BODY_SHA256", hashlib.sha256(raw.encode()).hexdigest()), patch.object(cap.subprocess, "run", return_value=response) as run:
            rows = cap.capture(REPO, "schedule", "", census(cap.PINNED_SOURCE_RUN))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["comment_id"], cap.PINNED_COMMENT)
        self.assertEqual(run.call_args.args[0], [
            "gh", "api", f"/repos/{REPO}/issues/comments/{cap.PINNED_COMMENT}"])

    def test_foreign_scheduled_recovery_fails_closed(self):
        with self.assertRaises(cap.RecoveryCaptureError):
            cap.capture("other/repo", "schedule", "", census(cap.PINNED_SOURCE_RUN))


if __name__ == "__main__":
    unittest.main()
