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


    def test_external_hour_dispatch_is_bounded_and_never_implicitly_publishes(self) -> None:
        required = (
            "run-name: \"Crypto source ingestion ${{ inputs.dispatch_correlation_id || github.run_id }}\"",
            "intended_hour_utc:",
            "dispatch_correlation_id:",
            'test "$GITHUB_REF" = "refs/heads/main"',
            "python scripts/crypto_ingestion_slot.py request",
            "python scripts/crypto_ingestion_slot.py prepare",
            "python scripts/crypto_ingestion_slot.py vacant",
            "python scripts/crypto_ingestion_slot.py accept",
            "crypto-hour-final-existing.json",
            "continue-on-error: true  # Rolling inspection PR is not source-publication authority.",
            "name: ${{ steps.slot.outputs.artifact_name }}",
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)
        self.assertIn('group: crypto-source-ingestion', self.body)
        self.assertIn('cancel-in-progress: false', self.body)
        self.assertIn('retention-days: 35', self.body)
        self.assert_ordered(
            "- name: Validate bounded scheduler request",
            "- name: Validate source snapshot",
            "- name: Validate observation hour",
            "- name: Check source-hour acceptance vacancy",
            "- name: Commit generated snapshot",
            "- name: Upload immutable publication source intent",
            "- name: Push rolling automation branch",
            "- name: Create or update rolling snapshot PR",
            "- name: Recheck uniqueness immediately before accepted-hour upload",
            "- name: Prepare accepted-hour receipt",
            "- name: Upload accepted-hour receipt",
        )

    def test_publication_requires_verified_receipt_for_external_ingestion(self) -> None:
        generator = (ROOT / ".github/workflows/generate-deterministic-site-publication.yml").read_text(encoding="utf-8")
        merge_gate = (ROOT / ".github/workflows/deterministic-site-publication-gate.yml").read_text(encoding="utf-8")
        self.assertIn("github.event.workflow_run.event == 'workflow_dispatch'", generator)
        source_gate = generator.split('if [[ "$GITHUB_EVENT_NAME" == "workflow_run" ]]; then', 1)[1]
        self.assertIn('case "$TRIGGER_EVENT" in', source_gate)
        self.assertIn('schedule|workflow_dispatch) ;;', source_gate)
        self.assertIn('*) echo "Unsupported ingestion event" >&2; exit 1 ;;', source_gate)
        self.assertLess(source_gate.index('case "$TRIGGER_EVENT" in'),
                        source_gate.index('case "$ACTIVATION" in'))
        self.assertIn("if: steps.source.outputs.proof_mode == 'false'", generator)
        self.assertIn('gh run download "$SOURCE_RUN_ID"', generator)
        self.assertIn("python scripts/deterministic_ingestion_provenance.py verify", generator)
        self.assertLess(generator.index("Independently verify source run and accepted-hour dispatch receipt"),
                        generator.index("Generate deterministic Markdown report"))
        self.assertIn('gh run download "$source_run_id"', merge_gate)
        self.assertIn('--source-receipt-json "$WORK/source-receipt.json"', merge_gate)
        self.assertLess(merge_gate.index("Independently verify immutable source-run provenance"),
                        merge_gate.index("Build credential-free gate facts"))


if __name__ == "__main__":
    unittest.main()
