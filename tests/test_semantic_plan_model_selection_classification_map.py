from __future__ import annotations

import unittest

from llm_analysis.evaluation import EvaluationIntegrityError
from llm_analysis.semantic_plan_model_evaluation import _validated_classification_map


class SemanticPlanModelSelectionClassificationMapTests(unittest.TestCase):
    def test_preserves_valid_case_classification_mapping(self) -> None:
        source = {
            "historical-normal-crosschecked": "public-market-data",
            "adversarial-prompt-injection": "evaluation-only",
        }

        result = _validated_classification_map(source)

        self.assertEqual(result, source)
        self.assertIsNot(result, source)

    def test_rejects_record_sequence_instead_of_reinterpreting_it(self) -> None:
        with self.assertRaisesRegex(EvaluationIntegrityError, "non-empty mapping"):
            _validated_classification_map(  # type: ignore[arg-type]
                [
                    {
                        "case_key": "historical-normal-crosschecked",
                        "classification": "public-market-data",
                    }
                ]
            )

    def test_rejects_empty_case_key(self) -> None:
        with self.assertRaisesRegex(EvaluationIntegrityError, "invalid case key"):
            _validated_classification_map({"": "public-market-data"})

    def test_rejects_empty_classification(self) -> None:
        with self.assertRaisesRegex(EvaluationIntegrityError, "invalid classification"):
            _validated_classification_map({"historical-normal-crosschecked": ""})


if __name__ == "__main__":
    unittest.main()
