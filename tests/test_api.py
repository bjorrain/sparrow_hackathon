import unittest

from fastapi.testclient import TestClient

from sparrow.backend.api import create_app
from sparrow.backend.parsers.clinical_parser import ClinicalDescriptionParser


class ClinicalExtractionApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = ClinicalDescriptionParser()

    def setUp(self) -> None:
        self.client = self.enterContext(TestClient(create_app(self.parser)))

    def test_extract_returns_classified_findings(self) -> None:
        response = self.client.post(
            "/extract",
            json={"text": "Артерия проходима. Выявлена киста."},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            [finding["status"] for finding in body["findings"]],
            ["норма", "патология"],
        )
        self.assertEqual(
            [finding["urgency"] for finding in body["findings"]],
            ["норма", "планово"],
        )
        self.assertEqual(
            body["findings"][1]["summary"],
            "Выявлена киста",
        )
        self.assertEqual(
            set(body["findings"][1]),
            {"summary", "status", "urgency"},
        )
        self.assertNotIn("lemmas", body["findings"][1])
        self.assertNotIn("status_rule", body["findings"][1])
        self.assertNotIn("urgency_rule", body["findings"][1])
        self.assertIn("structured_data", body)
        self.assertEqual(body["structured_data"]["структуры"], {})
        self.assertEqual(body["structured_data"]["стороны"], {})

    def test_extract_includes_structured_organ_fields(self) -> None:
        response = self.client.post(
            "/extract",
            json={
                "text": (
                    "Описание\n"
                    "Ультразвуковое исследование органов малого таза\n"
                    "Исследование проводилось на аппарате: ACUSON\n"
                    "МАТКА\n"
                    "Размеры: 72х59х64 мм"
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        structured_data = response.json()["structured_data"]
        self.assertEqual(
            structured_data["служебная_информация"]["аппарат"],
            "ACUSON",
        )
        self.assertEqual(
            structured_data["структуры"]["матка"]["размеры"],
            "72х59х64 мм",
        )

    def test_extract_does_not_return_fragment_title_or_study_type_as_findings(
        self,
    ) -> None:
        response = self.client.post(
            "/extract",
            json={
                "text": (
                    "Описание\n"
                    "УЛЬТРАЗВУКОВОЕ ИССЛЕДОВАНИЕ ОРГАНОВ МАЛОГО ТАЗА\n"
                    "МАТКА\n"
                    "Размеры: 72х59х64 мм\n"
                    "Достоверно узловых образований не определяется"
                )
            },
        )

        body = response.json()
        finding_text = "\n".join(
            item["summary"] for item in body["findings"]
        ).lower()
        self.assertNotIn("описание", finding_text)
        self.assertNotIn("ультразвуковое исследование", finding_text)
        self.assertEqual(
            body["structured_data"]["служебная_информация"]["тип_исследования"],
            "УЛЬТРАЗВУКОВОЕ ИССЛЕДОВАНИЕ ОРГАНОВ МАЛОГО ТАЗА",
        )

    def test_extract_classifies_negated_changes_as_normal(self) -> None:
        response = self.client.post(
            "/extract",
            json={
                "text": (
                    "Описание\n"
                    "ПРЕДСТАТЕЛЬНАЯ ЖЕЛЕЗА\n"
                    "Структуры не изменены.\n"
                    "Объем не увеличен."
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        findings = response.json()["findings"]
        self.assertEqual(
            [finding["summary"] for finding in findings],
            ["Структуры не изменены"],
        )
        self.assertEqual(
            [finding["status"] for finding in findings],
            ["норма"],
        )

    def test_extract_groups_vascular_measurements_by_side_and_vessel(self) -> None:
        response = self.client.post(
            "/extract",
            json={
                "text": (
                    "Описание\nСПРАВА:\nОБА Vps – 87 см/сек "
                    "(норма 55-103, 90-145)\nСЛЕВА:\n"
                    "ОБА Vps – 109 см/сек (норма 55-103, 90-145)"
                )
            },
        )

        structured = response.json()["structured_data"]
        self.assertEqual(
            structured["стороны"]["справа"]["сосуды"]["ОБА"]["измерения"][
                "Vps"
            ]["значение"],
            "87 см/сек",
        )
        self.assertEqual(
            structured["стороны"]["слева"]["сосуды"]["ОБА"]["измерения"][
                "Vps"
            ]["значение"],
            "109 см/сек",
        )

    def test_extract_rejects_blank_description(self) -> None:
        response = self.client.post("/extract", json={"text": "  \n "})

        self.assertEqual(response.status_code, 422)

    def test_extract_rejects_missing_and_extra_fields(self) -> None:
        missing = self.client.post("/extract", json={})
        extra = self.client.post(
            "/extract",
            json={"text": "Норма.", "unexpected": True},
        )

        self.assertEqual(missing.status_code, 422)
        self.assertEqual(extra.status_code, 422)

    def test_extract_rejects_oversized_description(self) -> None:
        response = self.client.post("/extract", json={"text": "а" * 100_001})

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
