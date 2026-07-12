from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.validate_documentation import validate_repository

ROOT = Path(__file__).resolve().parents[1]


class DocumentationValidationTests(unittest.TestCase):
    def make_repository(self) -> tuple[tempfile.TemporaryDirectory[str], Path, list[str]]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        files = {
            "README.md": "# Demo\n\n[Documentation](docs/index.md)\n",
            "docs/index.md": (
                "# Documentation\n\n"
                "### Tutorials\n\n"
                "- [Tutorial](tutorials/start.md)\n\n"
                "### How-to guides\n\n"
                "- [How-to](how-to/run.md)\n\n"
                "### Reference\n\n"
                "- [Reference](reference/contract.md)\n\n"
                "### Explanation\n\n"
                "- [Explanation](explanation/design.md)\n"
            ),
            "docs/tutorials/start.md": "# Start here\n\n[Contract](../reference/contract.md#fields)\n",
            "docs/how-to/run.md": "# Run the task\n",
            "docs/reference/contract.md": "# Contract\n\n## Fields\n",
            "docs/explanation/design.md": "# Design\n",
        }
        for relative_path, content in files.items():
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return temporary, root, sorted(files)

    def test_valid_repository_passes(self) -> None:
        temporary, root, tracked = self.make_repository()
        self.addCleanup(temporary.cleanup)
        self.assertEqual(validate_repository(root, tracked=tracked), [])

    def test_missing_target_is_reported(self) -> None:
        temporary, root, tracked = self.make_repository()
        self.addCleanup(temporary.cleanup)
        (root / "README.md").write_text("# Demo\n\n[Missing](docs/missing.md)\n", encoding="utf-8")
        codes = {item.code for item in validate_repository(root, tracked=tracked)}
        self.assertIn("missing-target", codes)

    def test_repository_escape_is_reported(self) -> None:
        temporary, root, tracked = self.make_repository()
        self.addCleanup(temporary.cleanup)
        (root / "README.md").write_text("# Demo\n\n[Outside](../outside.md)\n", encoding="utf-8")
        codes = {item.code for item in validate_repository(root, tracked=tracked)}
        self.assertIn("repository-escape", codes)

    def test_missing_anchor_is_reported(self) -> None:
        temporary, root, tracked = self.make_repository()
        self.addCleanup(temporary.cleanup)
        (root / "README.md").write_text(
            "# Demo\n\n[Contract](docs/reference/contract.md#missing)\n", encoding="utf-8"
        )
        codes = {item.code for item in validate_repository(root, tracked=tracked)}
        self.assertIn("missing-anchor", codes)

    def test_duplicate_mode_navigation_is_reported(self) -> None:
        temporary, root, tracked = self.make_repository()
        self.addCleanup(temporary.cleanup)
        index = root / "docs/index.md"
        index.write_text(
            index.read_text(encoding="utf-8").replace(
                "- [Tutorial](tutorials/start.md)",
                "- [Tutorial](tutorials/start.md)\n- [Duplicate](tutorials/start.md)",
            ),
            encoding="utf-8",
        )
        codes = {item.code for item in validate_repository(root, tracked=tracked)}
        self.assertIn("duplicate-navigation", codes)

    def test_wrong_mode_navigation_is_reported(self) -> None:
        temporary, root, tracked = self.make_repository()
        self.addCleanup(temporary.cleanup)
        index = root / "docs/index.md"
        index.write_text(
            index.read_text(encoding="utf-8").replace(
                "- [Tutorial](tutorials/start.md)",
                "- [Tutorial](reference/contract.md)",
            ),
            encoding="utf-8",
        )
        codes = {item.code for item in validate_repository(root, tracked=tracked)}
        self.assertIn("wrong-navigation-mode", codes)

    def test_removed_document_path_is_reported(self) -> None:
        temporary, root, tracked = self.make_repository()
        self.addCleanup(temporary.cleanup)
        removed = root / "docs/old.md"
        removed.write_text("# Old\n", encoding="utf-8")
        tracked.append("docs/old.md")
        (root / "README.md").write_text("# Demo\n\n[Old](docs/old.md)\n", encoding="utf-8")
        diagnostics = validate_repository(
            root,
            tracked=tracked,
            removed_paths=frozenset({"docs/old.md"}),
        )
        self.assertIn("removed-document-path", {item.code for item in diagnostics})

    def test_tracked_site_output_is_reported(self) -> None:
        temporary, root, tracked = self.make_repository()
        self.addCleanup(temporary.cleanup)
        site_file = root / "_site/index.html"
        site_file.parent.mkdir(parents=True, exist_ok=True)
        site_file.write_text("generated", encoding="utf-8")
        diagnostics = validate_repository(root, tracked=[*tracked, "_site/index.html"])
        self.assertIn("committed-generated-site", {item.code for item in diagnostics})

    def test_current_repository_documentation_is_valid(self) -> None:
        diagnostics = validate_repository(ROOT)
        self.assertEqual([item.render() for item in diagnostics], [])


if __name__ == "__main__":
    unittest.main()
