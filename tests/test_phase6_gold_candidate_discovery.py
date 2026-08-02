from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from llm_analysis.claim_candidate_gold_corpus import (
    ClaimCandidateGoldCorpusError,
    evaluate_claim_candidate_gold_corpus,
    load_claim_candidate_gold_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "evaluation" / "phase-06" / "claim-candidate-gold"


class Phase6GoldCandidateCorpusTests(unittest.TestCase):
    def test_checked_in_summary_and_review_are_byte_stable(self) -> None:
        result = evaluate_claim_candidate_gold_corpus(ROOT)

        self.assertEqual(result.summary_bytes, (GOLD / "summary.json").read_bytes())
        self.assertEqual(result.report_markdown, (GOLD / "review.md").read_bytes())
        self.assertEqual(result.summary["overall"]["status"], "pass")
        self.assertEqual(result.summary["overall"]["candidate_recall"], 1.0)
        self.assertEqual(result.summary["overall"]["expected_useful_count"], 38)
        self.assertEqual(result.summary["overall"]["resolved_expected_count"], 38)
        self.assertEqual(result.summary["overall"]["forbidden_check_count"], 20)
        self.assertEqual(result.summary["overall"]["forbidden_match_count"], 0)

    def test_case_classification_and_normalisation_boundary_are_explicit(self) -> None:
        result = evaluate_claim_candidate_gold_corpus(ROOT).summary
        classifications = {item["key"]: item["classification"] for item in result["cases"]}

        self.assertEqual(
            classifications,
            {
                "historical-degraded-sparse": "historical",
                "historical-normal-crosschecked": "historical",
                "historical-material-move": "historical",
                "adversarial-prompt-injection": "evaluation-only",
                "adversarial-source-disagreement": "evaluation-only",
            },
        )
        probe = result["normalisation_probe"]
        self.assertEqual(probe["classification"], "evaluation-only")
        self.assertTrue(probe["new_bundle_identity"])
        self.assertNotEqual(probe["previous_bundle_id"], probe["bundle_id"])
        self.assertEqual(
            probe["resolved_candidate_id"],
            "claim-candidate:sha256:066f8703cf8e4204a7a35fc74f15d136ad3d17b326770116e6c1dbc160ce3497",
        )
        self.assertTrue(probe["expected_features_match"])

    def test_phase5_corpus_byte_drift_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in (
                "config/llm-evaluation.yml",
                "evaluation/phase-05/corpus.yml",
                "evaluation/phase-06/claim-candidate-gold/manifest.yml",
                "evaluation/phase-06/claim-candidate-gold/normalisation-probe.yml",
            ):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            for source in (GOLD / "cases").glob("*.yml"):
                target = root / "evaluation/phase-06/claim-candidate-gold/cases" / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)

            corpus = root / "evaluation/phase-05/corpus.yml"
            corpus.write_text(corpus.read_text(encoding="utf-8") + "\n", encoding="utf-8")

            with self.assertRaises(ClaimCandidateGoldCorpusError) as raised:
                load_claim_candidate_gold_manifest(root)
            self.assertEqual(raised.exception.code, "corpus_blob_mismatch")

    def test_gold_path_contains_no_model_provider_or_publication_execution(self) -> None:
        source = (ROOT / "llm_analysis/claim_candidate_gold_corpus.py").read_text(encoding="utf-8")
        for prohibited in (
            "OpenRouterClient",
            "urllib.request",
            "api_key",
            "selected_candidate_ids",
            "render_claim_plan(",
            "_site/",
        ):
            self.assertNotIn(prohibited, source)

        summary = json.loads((GOLD / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["version"], "phase-06-claim-candidate-gold-summary/v1")
        self.assertTrue(all(item["deterministic_permutation"] for item in summary["cases"]))
