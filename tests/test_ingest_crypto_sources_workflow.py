from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ingest-crypto-sources.yml"


class IngestCryptoSourcesWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.body = WORKFLOW.read_text(encoding="utf-8")

    def assert_ordered(self, *markers: str) -> None:
        for marker in markers:
            self.assertIn(marker, self.body)
        positions = [self.body.index(marker) for marker in markers]
        self.assertEqual(positions, sorted(positions), markers)

    def test_workflow_uses_stable_rolling_branch_and_pr_title(self) -> None:
        required_markers = [
            'branch="automation/source-snapshot-rolling"',
            'title = "Update rolling crypto source snapshot"',
            "Branch: `automation/source-snapshot-rolling`.",
        ]
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)

        self.assertNotIn("automation/crypto-source-ingestion-${GITHUB_RUN_ID}", self.body)
        self.assertNotIn("Add crypto source snapshot {snapshot_path.stem}", self.body)

    def test_workflow_can_create_or_update_rolling_pr(self) -> None:
        required_markers = [
            "existing_pr=\"$(gh pr list",
            "--head \"$PUBLISH_BRANCH\"",
            "Updating existing rolling generated snapshot PR #$existing_pr.",
            "gh pr edit \"$existing_pr\"",
            "Creating rolling generated snapshot PR.",
            "gh pr create",
        ]
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)

    def test_rolling_branch_is_pushed_with_force_with_lease(self) -> None:
        required_markers = [
            "git checkout -B \"$PUBLISH_BRANCH\"",
            "git fetch origin \"$PUBLISH_BRANCH\" || true",
            "git push --force-with-lease --set-upstream origin \"$PUBLISH_BRANCH\"",
        ]
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)

    def test_workflow_keeps_snapshot_commit_scope(self) -> None:
        required_markers = [
            "git status --porcelain --untracked-files=all -- data/crypto/hourly",
            "$2 !~ /^data\\/crypto\\/hourly\\//",
            "git add data/crypto/hourly",
            "Committed only generated source snapshots under `data/crypto/hourly/...`.",
            "Did not commit generated `_site/` output.",
        ]
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)

        self.assertNotIn("git add _site", self.body)

    def test_scope_limitations_are_preserved(self) -> None:
        required_markers = [
            "This PR adds source evidence only.",
            "This PR does not generate a Markdown market report.",
            "This PR does not call an LLM.",
            "This PR does not auto-merge.",
        ]
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)

        prohibited_markers = [
            "gh pr merge",
            "--auto",
            "python -m site_generator",
            "Generate deterministic Markdown report",
        ]
        for marker in prohibited_markers:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, self.body)

    def test_observation_hour_validation_and_evidence_are_required(self) -> None:
        required_markers = [
            "- name: Validate observation hour",
            'python scripts/validate_crypto_observation_hour.py "$SNAPSHOT_PATH"',
            'generated_at_utc = run.get("generated_at_utc", "not recorded")',
            'observation_hour_utc = run.get("observation_hour_utc", "not recorded")',
            "Actual `generated_at_utc`: `{generated_at_utc}`",
            "Containing `observation_hour_utc`: `{observation_hour_utc}`",
            "`observation_hour_utc` is the canonical UTC hour containing the actual generation time; it is not the exact capture time.",
            "Ran `python scripts/validate_crypto_observation_hour.py {snapshot_path.as_posix()}`.",
        ]
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)

    def test_publish_order_remains_safe(self) -> None:
        self.assert_ordered(
            "- name: Validate source snapshot",
            "- name: Validate observation hour",
            "- name: Build PR evidence",
            "- name: Inspect generated snapshot changes",
            "- name: Create rolling automation branch",
            "- name: Commit generated snapshot",
            "- name: Push rolling automation branch",
            "- name: Create or update rolling snapshot PR",
        )


if __name__ == "__main__":
    unittest.main()
