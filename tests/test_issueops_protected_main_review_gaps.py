from __future__ import annotations

import copy
import unittest
import urllib.parse

from issueops_dispatch import core
from issueops_dispatch import target_guard as guard

SHA = "a" * 40
DISPATCHER_RUN_ID = 777
SUBJECT_DIGEST = "d" * 64


def dispatcher_run() -> dict[str, object]:
    return {
        "id": DISPATCHER_RUN_ID,
        "run_attempt": 1,
        "event": "issue_comment",
        "head_sha": SHA,
        "path": core.DISPATCHER_WORKFLOW_PATH,
        "head_branch": "main",
        "actor": {"id": core.ACTOR_USER_ID, "login": core.ACTOR_LOGIN},
        "triggering_actor": {
            "id": core.ACTOR_USER_ID,
            "login": core.ACTOR_LOGIN,
        },
        "repository": {"full_name": core.REPOSITORY},
    }


def page_url(page: int, *, digest: str = SUBJECT_DIGEST) -> str:
    query = urllib.parse.urlencode(
        {
            "predicate_type": core.PREDICATE_TYPE,
            "per_page": 100,
            "page": page,
        }
    )
    return (
        f"https://api.github.com/repos/{core.REPOSITORY}/attestations/"
        f"sha256:{digest}?{query}"
    )


class PaginationFailClosedTests(unittest.TestCase):
    class API(guard.GitHubReadAPI):
        def __init__(self, responses: list[tuple[object, dict[str, str]]]) -> None:
            self.repository = core.REPOSITORY
            self.base = f"https://api.github.com/repos/{core.REPOSITORY}"
            self.token = "unused"
            self.responses = list(responses)
            self.calls = 0

        def _request_url(self, url: str):
            self.calls += 1
            if not self.responses:
                raise AssertionError(f"unexpected pagination request: {url}")
            return self.responses.pop(0)

    def test_valid_two_page_enumeration_remains_exhaustive(self) -> None:
        api = self.API(
            [
                (
                    {"attestations": [{"bundle_url": "https://one"}]},
                    {"Link": f'<{page_url(2)}>; rel="next"'},
                ),
                (
                    {"attestations": [{"bundle_url": "https://two"}]},
                    {},
                ),
            ]
        )
        items = api.list_attestations(SUBJECT_DIGEST)
        self.assertEqual(
            [item["bundle_url"] for item in items],
            ["https://one", "https://two"],
        )
        self.assertEqual(api.calls, 2)

    def test_malformed_nonempty_link_component_fails_closed(self) -> None:
        api = self.API(
            [
                (
                    {"attestations": [{"bundle_url": "https://one"}]},
                    {
                        "Link": (
                            "not-a-link, "
                            f'<{page_url(2)}>; rel="next"'
                        )
                    },
                )
            ]
        )
        with self.assertRaisesRegex(guard.GuardError, "malformed"):
            api.list_attestations(SUBJECT_DIGEST)
        self.assertEqual(api.calls, 1)

    def test_duplicate_next_relations_fail_closed(self) -> None:
        api = self.API(
            [
                (
                    {"attestations": []},
                    {
                        "Link": (
                            f'<{page_url(2)}>; rel="next", '
                            f'<{page_url(3)}>; rel="next"'
                        )
                    },
                )
            ]
        )
        with self.assertRaisesRegex(guard.GuardError, "multiple"):
            api.list_attestations(SUBJECT_DIGEST)

    def test_next_link_cannot_escape_exact_collection_path(self) -> None:
        api = self.API(
            [
                (
                    {"attestations": []},
                    {"Link": f'<{page_url(2, digest="e" * 64)}>; rel="next"'},
                )
            ]
        )
        with self.assertRaisesRegex(guard.GuardError, "exact collection path"):
            api.list_attestations(SUBJECT_DIGEST)

    def test_conflicting_header_casing_fails_closed(self) -> None:
        api = self.API(
            [
                (
                    {"attestations": []},
                    {
                        "Link": f'<{page_url(2)}>; rel="next"',
                        "link": f'<{page_url(3)}>; rel="next"',
                    },
                )
            ]
        )
        with self.assertRaisesRegex(guard.GuardError, "conflicting"):
            api.list_attestations(SUBJECT_DIGEST)


class DispatcherRunMetadataTests(unittest.TestCase):
    def test_required_dispatcher_run_metadata_is_fail_closed(self) -> None:
        cases: list[dict[str, object]] = []
        for key in (
            "id",
            "run_attempt",
            "event",
            "head_sha",
            "path",
            "head_branch",
            "actor",
            "triggering_actor",
            "repository",
        ):
            changed = copy.deepcopy(dispatcher_run())
            changed.pop(key)
            cases.append(changed)

        changed = dispatcher_run()
        changed["actor"] = []
        cases.append(changed)

        changed = dispatcher_run()
        changed["triggering_actor"] = "owner"
        cases.append(changed)

        changed = dispatcher_run()
        changed["repository"] = []
        cases.append(changed)

        changed = dispatcher_run()
        changed["repository"] = {"full_name": "8ft0-ai/other"}
        cases.append(changed)

        for run in cases:
            with self.subTest(run=run), self.assertRaises(guard.GuardError):
                guard.verify_dispatcher_run(
                    run,
                    dispatcher_run_id=DISPATCHER_RUN_ID,
                    source_sha=SHA,
                )

    def test_complete_dispatcher_run_metadata_still_passes(self) -> None:
        guard.verify_dispatcher_run(
            dispatcher_run(),
            dispatcher_run_id=DISPATCHER_RUN_ID,
            source_sha=SHA,
        )


if __name__ == "__main__":
    unittest.main()
