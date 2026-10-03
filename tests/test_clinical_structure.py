import unittest

from sparrow.backend.parsers.clinical_structure import ClinicalStructureParser


class ClinicalStructureParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = ClinicalStructureParser()

    def test_extracts_metadata_anatomy_conclusion_and_recommendations(self) -> None:
        report = """Описание
УЛЬТРАЗВУКОВОЕ ИССЛЕДОВАНИЕ ОРГАНОВ МАЛОГО ТАЗА
Исследование проводилось на аппарате: SIEMENS ACUSON REDWOOD
Дата последней менструации:29.07.2026.
МАТКА
В положении anteflexio
Размеры:72х59х64 мм
Толщина стенок матки симметричная
Достоверно узловых и очаговых образований не определяется
ПРАВЫЙ ЯИЧНИК
Размеры: 24х13х16 мм
Праровариально лоцируется анэхогенное однородное образование с четкими ровными контурами: 12х11мм (киста)
В позадиматочном пространстве свободной жидкости не определяется.
ЗАКЛЮЧЕНИЕ: УЗ-признаки параовариальной кисты справа.
Рекомендовано: консультация гинеколога."""

        result = self.parser.parse(report)

        self.assertEqual(
            result["служебная_информация"],
            {
                "тип_исследования": (
                    "УЛЬТРАЗВУКОВОЕ ИССЛЕДОВАНИЕ ОРГАНОВ МАЛОГО ТАЗА"
                ),
                "аппарат": "SIEMENS ACUSON REDWOOD",
                "дата_последней_менструации": "29.07.2026",
            },
        )
        organs = result["органы"]
        self.assertEqual(organs["матка"]["размеры"], "72х59х64 мм")
        self.assertEqual(
            organs["матка"]["толщина_стенок_матки"],
            "симметричная",
        )
        self.assertEqual(
            organs["матка"]["образования"],
            ["Достоверно узловых и очаговых образований не определяется"],
        )
        self.assertEqual(organs["правый_яичник"]["размеры"], "24х13х16 мм")
        self.assertEqual(
            organs["правый_яичник"]["образования"],
            [
                "Праровариально лоцируется анэхогенное однородное образование "
                "с четкими ровными контурами: 12х11мм (киста)"
            ],
        )
        self.assertEqual(
            result["прочие_находки"],
            ["В позадиматочном пространстве свободной жидкости не определяется"],
        )
        self.assertEqual(
            result["заключение"],
            "УЗ-признаки параовариальной кисты справа",
        )
        self.assertEqual(result["рекомендации"], "консультация гинеколога")

    def test_does_not_invent_missing_data(self) -> None:
        result = self.parser.parse("Описание\nМАТКА\nКонтуры: ровные")

        self.assertEqual(
            result["органы"],
            {"матка": {"контуры": "ровные"}},
        )
        self.assertIsNone(result["заключение"])
        self.assertIsNone(result["рекомендации"])


if __name__ == "__main__":
    unittest.main()
