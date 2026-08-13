from __future__ import annotations

import unittest
import urllib.error
import urllib.parse

from issueops_dispatch import core
from issueops_dispatch import target_guard as common
from issueops_dispatch import target_guard_main as guard

SUBJECT = "a" * 64


def subject_url(*, code_page: int | None = None) -> str:
    query = {
        "predicate_type": core.PREDICATE_TYPE,
        "per_page": 100,
    }
    if code_page is not None:
        query["page"] = code_page
    return (
        f"https://api.github.com/repos/{core.REPOSITORY}/attestations/"
        f"sha256:{SUBJECT}?{urllib.parse.urlencode(query)}"
    )


def guarded_http_error(code: int, *, page: int | None = None) -> common.GuardError:
    http_error = urllib.error.HTTPError(
        subject_url(code_page=page), code, "test", None, None
    )
    error = common.GuardError(f"test HTTP {code}")
    error.__cause__ = http_error
    return error


class FakeAPI:
    repository = core.REPOSITORY

    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def list_attestations(self, _: str):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, common.GuardError):
            raise outcome
        return outcome


class AttestationAvailabilityTests(unittest.TestCase):
    def test_initial_404_then_success(self) -> None:
        expected = [{"bundle_url": "https://github.com/example"}]
        api = FakeAPI([guarded_http_error(404), expected])
        sleeps: list[float] = []
        actual = guard.wait_for_attestations(
            api, SUBJECT, enumerations=2, interval_seconds=5, sleep_fn=sleeps.append
        )
        self.assertEqual(actual, expected)
        self.assertEqual(api.calls, 2)
        self.assertEqual(sleeps, [5])

    def test_repeated_404_exhausts_bound(self) -> None:
        api = FakeAPI([guarded_http_error(404), guarded_http_error(404)])
        with self.assertRaisesRegex(common.GuardError, "bounded wait"):
            guard.wait_for_attestations(
                api, SUBJECT, enumerations=2, interval_seconds=0, sleep_fn=lambda _: None
            )
        self.assertEqual(api.calls, 2)

    def test_other_http_failures_are_not_absence(self) -> None:
        for code in (403, 500):
            with self.subTest(code=code):
                api = FakeAPI([guarded_http_error(code)])
                with self.assertRaises(common.GuardError):
                    guard.wait_for_attestations(
                        api,
                        SUBJECT,
                        enumerations=2,
                        interval_seconds=0,
                        sleep_fn=lambda _: self.fail("unexpected retry"),
                    )
                self.assertEqual(api.calls, 1)

    def test_pagination_404_is_not_absence(self) -> None:
        api = FakeAPI([guarded_http_error(404, page=2)])
        with self.assertRaises(common.GuardError):
            guard.wait_for_attestations(
                api,
                SUBJECT,
                enumerations=2,
                interval_seconds=0,
                sleep_fn=lambda _: self.fail("unexpected retry"),
            )
        self.assertEqual(api.calls, 1)

    def test_network_failure_is_not_absence(self) -> None:
        error = common.GuardError("test network failure")
        error.__cause__ = urllib.error.URLError("test")
        api = FakeAPI([error])
        with self.assertRaises(common.GuardError):
            guard.wait_for_attestations(
                api,
                SUBJECT,
                enumerations=2,
                interval_seconds=0,
                sleep_fn=lambda _: self.fail("unexpected retry"),
            )
        self.assertEqual(api.calls, 1)

    def test_polling_bound_is_unchanged(self) -> None:
        self.assertEqual(guard.ATTESTATION_ENUMERATIONS, 12)
        self.assertEqual(guard.ATTESTATION_INTERVAL_SECONDS, 5)


if __name__ == "__main__":
    unittest.main()
