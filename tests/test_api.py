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
        self.assertIn("status_rule", body["findings"][1])
        self.assertIn("structured_data", body)
        self.assertEqual(body["structured_data"]["органы"], {})

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
            structured_data["органы"]["матка"]["размеры"],
            "72х59х64 мм",
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
