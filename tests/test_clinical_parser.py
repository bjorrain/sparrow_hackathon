import unittest

from sparrow.backend.parsers.clinical_parser import ClinicalDescriptionParser


class ClinicalDescriptionParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = ClinicalDescriptionParser()

    def test_extracts_findings_and_classifies_normal_and_pathology(self) -> None:
        result = self.parser.parse(
            "Артерия проходима. Выявлена киста; стеноз не определяется."
        )

        findings = result["findings"]
        self.assertEqual(
            [finding["status"] for finding in findings],
            ["норма", "патология", "норма"],
        )
        self.assertEqual(
            [finding["urgency"] for finding in findings],
            ["норма", "планово", "норма"],
        )

    def test_classifies_measurement_change_and_explicit_urgency(self) -> None:
        result = self.parser.parse(
            "КИМ повышен до 1,1 мм; требуется срочная консультация."
        )

        self.assertEqual(
            [finding["status"] for finding in result["findings"]],
            ["изменение", "изменение"],
        )
        self.assertEqual(
            [finding["urgency"] for finding in result["findings"]],
            ["планово", "срочно"],
        )

    def test_adds_custom_urgency_terms(self) -> None:
        parser = ClinicalDescriptionParser(
            urgency_rules={"срочно": ["немедленная консультация"]}
        )

        finding = parser.parse("Немедленная консультация.")["findings"][0]

        self.assertEqual(finding["urgency"], "срочно")
        self.assertEqual(finding["summary"], "Немедленная консультация.")

    def test_keeps_laterality_with_finding_and_handles_negated_change(self) -> None:
        result = self.parser.parse("СПРАВА:\nОтклонений от нормы не выявлено.")

        self.assertEqual(len(result["findings"]), 1)
        self.assertTrue(result["findings"][0]["summary"].startswith("СПРАВА"))
        self.assertEqual(result["findings"][0]["status"], "норма")

    def test_reference_range_does_not_by_itself_imply_normality(self) -> None:
        result = self.parser.parse("Vps 109 см/сек (норма 55-103).")

        finding = result["findings"][0]
        self.assertEqual(finding["status"], "изменение")
        self.assertEqual(finding["summary"], "Vps 109 см/сек (норма 55-103).")

    def test_negated_urgency_does_not_raise_urgency_level(self) -> None:
        finding = self.parser.parse("Не срочно требуется консультация.")["findings"][0]

        self.assertEqual(finding["urgency"], "планово")

    def test_negated_changes_are_classified_as_normal(self) -> None:
        phrases = (
            "Структуры не изменены.",
            "Объем не увеличен.",
            "Мелкая протоковая система не расширена.",
            "Стенки пузырьков не утолщены.",
            "Без локальных и диффузных изменений васкуляризации.",
        )

        for phrase in phrases:
            with self.subTest(phrase=phrase):
                finding = self.parser.parse(phrase)["findings"][0]
                self.assertEqual(finding["status"], "норма")

    def test_positive_change_is_still_classified_as_change(self) -> None:
        for phrase in ("Структуры изменены.", "Объем увеличен."):
            with self.subTest(phrase=phrase):
                finding = self.parser.parse(phrase)["findings"][0]
                self.assertEqual(finding["status"], "изменение")

    def test_rejects_unknown_urgency_category(self) -> None:
        with self.assertRaises(ValueError):
            ClinicalDescriptionParser(urgency_rules={"когда-нибудь": ["позже"]})


if __name__ == "__main__":
    unittest.main()
