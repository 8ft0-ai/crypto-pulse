"""Production publication regression: commit-pinned Research Brief evidence."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import research_brief_v1 as brief

FIXTURE = ROOT / "data/crypto/hourly/2026/11/08/0807_AEDT_source_snapshot.json"
RELATIVE = Path("data/crypto/hourly/2026/11/08/0807_AEDT_source_snapshot.json")
GENERATION = ROOT / ".github/workflows/generate-deterministic-site-publication.yml"
GATE = ROOT / ".github/workflows/deterministic-site-publication-gate.yml"
BOT = "cryptopulse-deterministic-publication[bot]"
EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"
STAMP = "2026-11-08T08:00:00Z"
MESSAGE = "Archive deterministic crypto snapshot 123456-1"


def git(root: Path, *args: str, env: dict[str, str] | None = None) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True, capture_output=True, text=True, env=env, timeout=15,
    )
    return proc.stdout.strip()


def committed_snapshot(root: Path, snapshot: dict, *, commit: bool = True) -> tuple[Path, str | None]:
    path = root / RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, sort_keys=True), encoding="utf-8")
    if not commit:
        return path, None
    git(root, "add", RELATIVE.as_posix())
    env = dict(os.environ, GIT_AUTHOR_DATE=STAMP, GIT_COMMITTER_DATE=STAMP)
    git(root, "commit", "-m", MESSAGE, env=env)
    return path, git(root, "rev-parse", "HEAD")


class PublicationEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.name", BOT)
        git(self.root, "config", "user.email", EMAIL)
        (self.root / "README.md").write_text("trusted base\n", encoding="utf-8")
        git(self.root, "add", "README.md")
        git(self.root, "commit", "-m", "Trusted base")
        self.base = git(self.root, "rev-parse", "HEAD")
        self.snapshot = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def brief(self, snapshot: dict, path: Path) -> str:
        with patch.object(brief, "ROOT", self.root):
            return brief.research_brief(snapshot, path, snapshot["quality"])

    def test_committed_qualifying_snapshot_has_exact_resolving_evidence(self) -> None:
        path, _ = committed_snapshot(self.root, self.snapshot, commit=False)
        self.assertIn("immutable public link unavailable", self.brief(self.snapshot, path))
        self.assertNotIn("Seven-day relative movement", self.brief(self.snapshot, path))
        path, sha = committed_snapshot(self.root, self.snapshot)
        self.assertEqual(git(self.root, "rev-parse", "HEAD^"), self.base)
        self.assertEqual(git(self.root, "diff-tree", "--no-commit-id", "--name-only", "-r", sha), RELATIVE.as_posix())
        source = subprocess.run(
            ["git", "-C", str(self.root), "show", f"{sha}:{RELATIVE.as_posix()}"],
            check=True, capture_output=True, timeout=15,
        ).stdout
        self.assertEqual(source, path.read_bytes())
        digest = hashlib.sha256(source).hexdigest()
        content = self.brief(self.snapshot, path)
        self.assertIn(f"fixture://{sha}/{RELATIVE.as_posix()}", content)
        self.assertNotIn("https://github.com/8ft0-ai/crypto-pulse/blob/", content)
        self.assertIn(f"SHA-256 `{digest}`", content)
        self.assertIn("Seven-day relative movement", content)
        self.assertIn("-4.63 percentage points", content)
        self.assertIn("-5.94 percentage points", content)
        git(self.root, "reset", "--hard", self.base)
        _, second_sha = committed_snapshot(self.root, self.snapshot)
        self.assertEqual(sha, second_sha)

    def test_uncommitted_and_modified_evidence_fail_closed(self) -> None:
        path, _ = committed_snapshot(self.root, self.snapshot, commit=False)
        self.assertIn("No qualifying finding", self.brief(self.snapshot, path))
        _, sha = committed_snapshot(self.root, self.snapshot)
        self.assertIn(f"fixture://{sha}/", self.brief(self.snapshot, path))
        path.write_bytes(path.read_bytes() + b"\n")
        content = self.brief(self.snapshot, path)
        self.assertIn("immutable public link unavailable", content)
        self.assertIn("No qualifying finding", content)

    def test_nonqualifying_or_misaligned_observations_are_suppressed(self) -> None:
        for mode in ("below_threshold", "stale_source", "missing_source", "misaligned_source"):
            with self.subTest(mode=mode):
                git(self.root, "reset", "--hard", self.base)
                candidate = deepcopy(self.snapshot)
                candidate["exchange_crosscheck"]["sources"] = {}
                assets = candidate["market"]["assets"]
                if mode == "below_threshold":
                    for asset in assets:
                        if asset["symbol"] in ("SOL", "BTC", "ETH"):
                            asset["change_7d_pct"] = -2.0
                elif mode == "stale_source":
                    for asset in assets:
                        asset["last_updated"] = "2025-01-01T00:00:00Z"
                elif mode == "missing_source":
                    candidate["market"]["assets"] = [a for a in assets if a["symbol"] != "SOL"]
                elif mode == "misaligned_source":
                    for asset in assets:
                        if asset["symbol"] == "SOL":
                            asset["last_updated"] = "2026-11-08T00:00:00Z"
                path, sha = committed_snapshot(self.root, candidate)
                content = self.brief(candidate, path)
                self.assertIn(f"fixture://{sha}/", content)
                self.assertNotIn("Seven-day relative movement", content)
                self.assertIn("No qualifying finding", content)

    def test_publication_workflow_reproduces_pinned_commit_and_preserves_merge(self) -> None:
        workflow = GENERATION.read_text(encoding="utf-8")
        prepare, publish = workflow.split("\n  publish:", 1)
        self.assertLess(prepare.index("Independently verify source run and accepted-hour dispatch receipt"),
                        prepare.index("Create local immutable snapshot evidence commit"))
        self.assertLess(prepare.index("Create local immutable snapshot evidence commit"),
                        prepare.index("Generate deterministic Markdown report"))
        self.assertLess(prepare.index("Generate deterministic Markdown report"),
                        prepare.index("Validate deterministic report and repository proof"))
        self.assertIn('git diff --name-only "$GITHUB_SHA" HEAD', prepare)
        self.assertIn("evidence_commit_sha:", prepare)
        self.assertIn('GIT_AUTHOR_DATE="$OBSERVATION_HOUR_UTC" GIT_COMMITTER_DATE="$OBSERVATION_HOUR_UTC"', prepare)
        self.assertIn('GIT_AUTHOR_DATE="$OBSERVATION_HOUR_UTC" GIT_COMMITTER_DATE="$OBSERVATION_HOUR_UTC"', publish)
        self.assertLess(publish.index("Revalidate proof authority and disabled activation before App use"),
                        publish.index("Reproduce immutable snapshot evidence commit and publish report commit"))
        self.assertLess(publish.index("Reproduce immutable snapshot evidence commit and publish report commit"),
                        publish.index("Mint short-lived repository-scoped publication App token"))
        self.assertIn('test "$(git rev-parse HEAD)" = "$EVIDENCE_COMMIT_SHA"', publish)
        self.assertIn('test "$(git rev-parse HEAD^)" = "$GITHUB_SHA"', publish)
        self.assertIn('git show "HEAD:$SNAPSHOT_PATH" | cmp - "$SNAPSHOT_PATH"', publish)
        self.assertIn('grep -F "blob/$EVIDENCE_COMMIT_SHA/$SNAPSHOT_PATH"', publish)
        self.assertIn('test "$(git diff --cached --name-only)" = "$REPORT_PATH"', publish)
        self.assertIn("validate-scope", publish)
        self.assertIn("build-attestation", publish)
        self.assertIn("merge_method=merge", GATE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
