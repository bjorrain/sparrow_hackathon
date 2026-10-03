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

    def test_extract_returns_frontend_schema_with_per_structure_status(self) -> None:
        response = self.client.post(
            "/extract",
            json={
                "text": (
                    "Описание\n"
                    "ПЕЧЕНЬ\n"
                    "Размеры: 145 мм\n"
                    "Структура паренхимы: однородная\n"
                    "Толщина стенок: симметричная\n"
                    "ЖЕЛЧНЫЙ ПУЗЫРЬ\n"
                    "Выявлена киста 12 мм\n"
                    "ЗАКЛЮЧЕНИЕ: Простая киста печени\n"
                    "Рекомендовано: контрольное УЗИ"
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), {"structures", "technical_data", "conclusion"})
        self.assertEqual(
            set(body["structures"][0]),
            {"name", "size", "morphology", "status"},
        )
        self.assertEqual(
            body["structures"][0],
            {
                "name": "печень",
                "size": "145 мм",
                "morphology": {
                    "структура_паренхимы": "однородная",
                    "толщина_стенок": "симметричная",
                },
                "status": "норма",
            },
        )
        self.assertEqual(
            body["structures"][1]["status"],
            "патология",
        )
        self.assertEqual(
            body["structures"][1]["name"],
            "желчный пузырь",
        )
        self.assertEqual(
            body["conclusion"],
            {
                "text": "Простая киста печени",
                "recommendations": "контрольное УЗИ",
            },
        )
        self.assertEqual(body["technical_data"], {})

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
        body = response.json()
        self.assertEqual(
            body["technical_data"]["аппарат"],
            "ACUSON",
        )
        self.assertEqual(
            body["structures"][0]["name"],
            "матка",
        )
        uterus = next(item for item in body["structures"] if item["name"] == "матка")
        self.assertEqual(uterus["size"], "72х59х64 мм")

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
                    "Размеры: 72х59х64 мм, правильной формы\n"
                    "Достоверно узловых образований не определяется"
                )
            },
        )

        body = response.json()
        structure_names = " ".join(item["name"] for item in body["structures"]).lower()
        self.assertNotIn("описание", structure_names)
        self.assertNotIn("ультразвуковое исследование", structure_names)
        uterus = next(item for item in body["structures"] if item["name"] == "матка")
        self.assertEqual(uterus["size"], "72х59х64 мм")
        self.assertEqual(uterus["morphology"]["форма"], "правильной формы")
        self.assertEqual(
            body["technical_data"]["тип_исследования"],
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
        self.assertEqual(
            response.json()["structures"][0]["status"],
            "норма",
        )

    def test_extract_does_not_mark_negated_formation_as_pathology(self) -> None:
        response = self.client.post(
            "/extract",
            json={
                "text": (
                    "Описание\n"
                    "ШЕЙКА МАТКИ\n"
                    "В ее проекции дополнительных образований не визуализируется"
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["structures"][0]["status"], "норма")

    def test_extract_maps_explicit_change_to_suspicion(self) -> None:
        response = self.client.post(
            "/extract",
            json={
                "text": (
                    "Описание\n"
                    "ВЕНЫ\n"
                    "Умеренно извиты"
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["structures"][0]["status"],
            "подозрение",
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

        body = response.json()
        right_side = next(
            item for item in body["structures"] if item["name"] == "ОБА справа"
        )
        left_side = next(
            item for item in body["structures"] if item["name"] == "ОБА слева"
        )
        self.assertEqual(
            right_side["morphology"]["измерения"]["Vps"]["значение"],
            "87 см/сек",
        )
        self.assertEqual(
            left_side["morphology"]["измерения"]["Vps"]["значение"],
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
