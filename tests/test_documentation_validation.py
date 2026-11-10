from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.validate_documentation import validate_repository

ROOT = Path(__file__).resolve().parents[1]


def canonical_page(title: str, mode: str, body: str = "") -> str:
    return (
        f"# {title}\n\n"
        f"> **Mode:** {mode}  \n"
        "> **Audience:** Test readers  \n"
        "> **Outcome:** Complete the documented test outcome.\n\n"
        f"{body}"
    )


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
            "docs/tutorials/start.md": canonical_page(
                "Start here",
                "Tutorial",
                "[Contract](../reference/contract.md#fields)\n",
            ),
            "docs/how-to/run.md": canonical_page("Run the task", "How-to"),
            "docs/reference/contract.md": canonical_page(
                "Contract",
                "Reference",
                "## Fields\n",
            ),
            "docs/explanation/design.md": canonical_page("Design", "Explanation"),
        }
        for relative_path, content in files.items():
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return temporary, root, sorted(files)

    def diagnostic_codes(self, root: Path, tracked: list[str]) -> set[str]:
        return {item.code for item in validate_repository(root, tracked=tracked)}

    def test_valid_repository_passes(self) -> None:
        temporary, root, tracked = self.make_repository()
        self.addCleanup(temporary.cleanup)
        self.assertEqual(validate_repository(root, tracked=tracked), [])

    def test_missing_target_is_reported(self) -> None:
        temporary, root, tracked = self.make_repository()
        self.addCleanup(temporary.cleanup)
        (root / "README.md").write_text("# Demo\n\n[Missing](docs/missing.md)\n", encoding="utf-8")
        self.assertIn("missing-target", self.diagnostic_codes(root, tracked))

    def test_repository_escape_is_reported(self) -> None:
        temporary, root, tracked = self.make_repository()
        self.addCleanup(temporary.cleanup)
        (root / "README.md").write_text("# Demo\n\n[Outside](../outside.md)\n", encoding="utf-8")
        self.assertIn("repository-escape", self.diagnostic_codes(root, tracked))

    def test_missing_anchor_is_reported(self) -> None:
        temporary, root, tracked = self.make_repository()
        self.addCleanup(temporary.cleanup)
        (root / "README.md").write_text(
            "# Demo\n\n[Contract](docs/reference/contract.md#missing)\n", encoding="utf-8"
        )
        self.assertIn("missing-anchor", self.diagnostic_codes(root, tracked))

    def test_missing_image_target_is_reported(self) -> None:
        temporary, root, tracked = self.make_repository()
        self.addCleanup(temporary.cleanup)
        tutorial = root / "docs/tutorials/start.md"
        tutorial.write_text(
            tutorial.read_text(encoding="utf-8") + "\n![Diagram](../images/missing.png)\n",
            encoding="utf-8",
        )
        self.assertIn("missing-target", self.diagnostic_codes(root, tracked))

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
        self.assertIn("duplicate-navigation", self.diagnostic_codes(root, tracked))

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
        self.assertIn("wrong-navigation-mode", self.diagnostic_codes(root, tracked))

    def test_unindexed_canonical_page_is_reported(self) -> None:
        temporary, root, tracked = self.make_repository()
        self.addCleanup(temporary.cleanup)
        orphan = root / "docs/how-to/orphan.md"
        orphan.write_text(canonical_page("Orphan task", "How-to"), encoding="utf-8")
        tracked.append("docs/how-to/orphan.md")
        self.assertIn("unindexed-canonical-page", self.diagnostic_codes(root, tracked))

    def test_catalogue_target_must_be_tracked(self) -> None:
        temporary, root, tracked = self.make_repository()
        self.addCleanup(temporary.cleanup)
        target = root / "docs/how-to/untracked.md"
        target.write_text(canonical_page("Untracked task", "How-to"), encoding="utf-8")
        index = root / "docs/index.md"
        index.write_text(
            index.read_text(encoding="utf-8").replace(
                "- [How-to](how-to/run.md)",
                "- [How-to](how-to/untracked.md)",
            ),
            encoding="utf-8",
        )
        self.assertIn("untracked-navigation", self.diagnostic_codes(root, tracked))

    def test_catalogue_target_must_be_canonical(self) -> None:
        temporary, root, tracked = self.make_repository()
        self.addCleanup(temporary.cleanup)
        compatibility = root / "docs/legacy.md"
        compatibility.write_text("# Legacy pointer\n", encoding="utf-8")
        tracked.append("docs/legacy.md")
        index = root / "docs/index.md"
        index.write_text(
            index.read_text(encoding="utf-8").replace(
                "- [How-to](how-to/run.md)",
                "- [How-to](legacy.md)",
            ),
            encoding="utf-8",
        )
        self.assertIn("noncanonical-navigation", self.diagnostic_codes(root, tracked))

    def test_missing_h1_is_reported_for_canonical_page(self) -> None:
        temporary, root, tracked = self.make_repository()
        self.addCleanup(temporary.cleanup)
        page = root / "docs/how-to/run.md"
        page.write_text(page.read_text(encoding="utf-8").replace("# Run the task\n", ""), encoding="utf-8")
        self.assertIn("missing-h1", self.diagnostic_codes(root, tracked))

    def test_multiple_h1_is_reported_for_canonical_page(self) -> None:
        temporary, root, tracked = self.make_repository()
        self.addCleanup(temporary.cleanup)
        page = root / "docs/how-to/run.md"
        page.write_text(page.read_text(encoding="utf-8") + "\n# Second title\n", encoding="utf-8")
        self.assertIn("multiple-h1", self.diagnostic_codes(root, tracked))

    def test_missing_metadata_is_reported_for_canonical_page(self) -> None:
        temporary, root, tracked = self.make_repository()
        self.addCleanup(temporary.cleanup)
        page = root / "docs/how-to/run.md"
        page.write_text(
            page.read_text(encoding="utf-8").replace(
                "> **Outcome:** Complete the documented test outcome.\n",
                "",
            ),
            encoding="utf-8",
        )
        self.assertIn("missing-page-metadata", self.diagnostic_codes(root, tracked))

    def test_declared_mode_must_match_directory(self) -> None:
        temporary, root, tracked = self.make_repository()
        self.addCleanup(temporary.cleanup)
        page = root / "docs/how-to/run.md"
        page.write_text(
            page.read_text(encoding="utf-8").replace("**Mode:** How-to", "**Mode:** Reference"),
            encoding="utf-8",
        )
        self.assertIn("declared-mode-mismatch", self.diagnostic_codes(root, tracked))

    def test_invalid_canonical_filename_is_reported(self) -> None:
        temporary, root, tracked = self.make_repository()
        self.addCleanup(temporary.cleanup)
        valid = root / "docs/how-to/run.md"
        invalid = root / "docs/how-to/Invalid_Name.md"
        invalid.write_text(valid.read_text(encoding="utf-8"), encoding="utf-8")
        tracked.remove("docs/how-to/run.md")
        tracked.append("docs/how-to/Invalid_Name.md")
        index = root / "docs/index.md"
        index.write_text(
            index.read_text(encoding="utf-8").replace("how-to/run.md", "how-to/Invalid_Name.md"),
            encoding="utf-8",
        )
        self.assertIn("invalid-document-filename", self.diagnostic_codes(root, tracked))

    def test_noncanonical_markdown_is_exempt_from_page_structure(self) -> None:
        temporary, root, tracked = self.make_repository()
        self.addCleanup(temporary.cleanup)
        records = {
            "docs/legacy.md": "Compatibility pointer without metadata.\n",
            "planning/review.md": "Historical review without metadata.\n",
            "evaluation/evidence.md": "Evaluation evidence without metadata.\n",
        }
        for relative_path, content in records.items():
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            tracked.append(relative_path)
        structure_codes = {
            "missing-h1",
            "multiple-h1",
            "missing-page-metadata",
            "duplicate-page-metadata",
            "declared-mode-mismatch",
            "invalid-document-filename",
            "unindexed-canonical-page",
        }
        self.assertTrue(structure_codes.isdisjoint(self.diagnostic_codes(root, tracked)))

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
