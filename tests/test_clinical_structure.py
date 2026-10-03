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
При исследовании в режиме ЦДК - кровоток не усилен
Полость матки не деформирована,не расширена
ПРАВЫЙ ЯИЧНИК
Размеры: 24х13х16 мм
Расположен типично.
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
        structures = result["структуры"]
        self.assertEqual(structures["матка"]["размеры"], "72х59х64 мм")
        self.assertEqual(
            structures["матка"]["толщина_стенок_матки"],
            "симметричная",
        )
        self.assertEqual(
            structures["матка"]["наблюдения"],
            [
                "Достоверно узловых и очаговых образований не определяется",
                "При исследовании в режиме ЦДК - кровоток не усилен",
                "Полость матки не деформирована,не расширена",
            ],
        )
        self.assertEqual(
            structures["правый_яичник"]["размеры"],
            "24х13х16 мм",
        )
        self.assertEqual(
            structures["правый_яичник"]["образования"],
            [
                "Праровариально лоцируется анэхогенное однородное образование "
                "с четкими ровными контурами: 12х11мм (киста)"
            ],
        )
        self.assertEqual(
            structures["правый_яичник"]["расположение"],
            "типично",
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
            result["структуры"],
            {"матка": {"контуры": "ровные"}},
        )
        self.assertIsNone(result["заключение"])
        self.assertIsNone(result["рекомендации"])

    def test_extracts_unknown_anatomical_sections_dynamically(self) -> None:
        result = self.parser.parse(
            "Описание\n"
            "УЛЬТРАЗВУКОВОЕ ИССЛЕДОВАНИЕ\n"
            "ПЕЧЕНЬ\n"
            "Размеры: 145 мм\n"
            "МОЧЕВОЙ ПУЗЫРЬ\n"
            "Стенки: не утолщены"
        )

        self.assertEqual(
            result["структуры"],
            {
                "печень": {"размеры": "145 мм"},
                "мочевой_пузырь": {"стенки": "не утолщены"},
            },
        )

    def test_extracts_title_case_structure_and_arbitrary_labeled_fields(self) -> None:
        result = self.parser.parse(
            "Описание\n"
            "Протокол ультразвукового исследования\n"
            "Магистральные сосуды:\n"
            "Диаметр сосуда: 5 мм"
        )

        self.assertEqual(
            result["структуры"],
            {"магистральные_сосуды": {"диаметр_сосуда": "5 мм"}},
        )

    def test_keeps_study_title_before_description_in_metadata(self) -> None:
        result = self.parser.parse(
            "Исследование щитовидной железы\n"
            "Описание\n"
            "ЩИТОВИДНАЯ ЖЕЛЕЗА\n"
            "Объем: 10 мл"
        )

        self.assertEqual(
            result["служебная_информация"]["тип_исследования"],
            "Исследование щитовидной железы",
        )
        self.assertEqual(
            result["структуры"],
            {"щитовидная_железа": {"объем": "10 мл"}},
        )

    def test_structures_prostate_report_zones_and_adjacent_organs(self) -> None:
        result, clinical_text = self.parser.parse_with_clinical_text(
            "Описание\n"
            "ПРЕДСТАТЕЛЬНАЯ ЖЕЛЕЗА, ТРУЗИ\n"
            "Форма: обычная\n"
            "Контуры: ровные, четкие\n"
            "Структура:\n"
            "- В переходных зонах и области периуретральных желез – "
            "диффузно неоднородная с участками краевого фиброза и "
            "микрокальцинатами, не увеличена, мелкая протоковая система "
            "не расширена\n"
            "В центральных зонах – однородная\n"
            "В периферических зонах – однородная\n"
            "Эхогенность предстательной железы – средняя\n"
            "Размеры – 45х35х24 мм\n"
            "Объем – 19,8 см3 (норма до 25 см3)\n"
            "Простатическая часть уретры – не деформирована\n"
            "Уретральный канал и шейка мочевого пузыря не деформированы\n"
            "Семенные пузырьки: поперечник 10 мм, однородные, "
            "гипоэхогенные, стенки не утолщены\n"
            "Перипростатические вены не расширены, умеренно извиты"
        )

        prostate = result["структуры"]["предстательная_железа"]
        self.assertEqual(
            result["служебная_информация"]["тип_исследования"], "ТРУЗИ"
        )
        self.assertEqual(prostate["размеры"], "45х35х24 мм")
        self.assertEqual(
            prostate["объем"],
            {"значение": "19,8 см3", "референс": "норма до 25 см3"},
        )
        self.assertEqual(len(prostate["структура"]), 3)
        self.assertEqual(
            prostate["семенные_пузырьки"]["поперечник"], "10 мм"
        )
        self.assertEqual(
            prostate["семенные_пузырьки"]["стенки"], "не утолщены"
        )
        self.assertEqual(
            prostate["простатическая_часть_уретры"]["состояние"],
            "не деформирована",
        )
        self.assertNotIn("Структура", clinical_text)
        self.assertNotIn("10 мм", clinical_text)
        self.assertIn("не увеличена", clinical_text)
        self.assertIn("умеренно извиты", clinical_text)

    def test_extracts_service_fields_without_misclassifying_free_findings(self) -> None:
        result = self.parser.parse(
            "Описание\n"
            "УЗИ почек\n"
            "Датчик: 10L4\n"
            "Свободная жидкость: не определяется"
        )

        self.assertEqual(
            result["служебная_информация"],
            {"тип_исследования": "УЗИ почек", "датчик": "10L4"},
        )
        self.assertEqual(
            result["прочие_находки"],
            ["Свободная жидкость: не определяется"],
        )

    def test_skips_fragment_title_and_study_type_in_clinical_text(self) -> None:
        _, clinical_text = self.parser.parse_with_clinical_text(
            "Описание\n"
            "УЛЬТРАЗВУКОВОЕ ИССЛЕДОВАНИЕ ОРГАНОВ МАЛОГО ТАЗА\n"
            "МАТКА\n"
            "Достоверно узловых образований не определяется"
        )

        self.assertNotIn("Описание", clinical_text)
        self.assertNotIn("УЛЬТРАЗВУКОВОЕ ИССЛЕДОВАНИЕ", clinical_text)
        self.assertIn("узловых образований", clinical_text)

    def test_groups_vessel_measurements_by_side_and_yargy_vessel_match(self) -> None:
        result = self.parser.parse(
            "Описание\n"
            "СПРАВА:\n"
            "Артерии осмотрены, проходимы.\n"
            "ОБА Vps – 87 см/сек (норма 55-103, 90-145)\n"
            "\n"
            "ПБА Vps – 76 см/сек (норма 51-77, 70-110)\n"
            "СЛЕВА:\n"
            "ОБА Vps – 109 см/сек (норма 55-103, 90-145)"
        )

        sides = result["стороны"]
        self.assertEqual(
            sides["справа"]["сосуды"]["ОБА"]["измерения"]["Vps"],
            {
                "значение": "87 см/сек",
                "референс": "норма 55-103, 90-145",
            },
        )
        self.assertEqual(
            sides["справа"]["сосуды"]["ПБА"]["измерения"]["Vps"],
            {
                "значение": "76 см/сек",
                "референс": "норма 51-77, 70-110",
            },
        )
        self.assertEqual(
            sides["слева"]["сосуды"]["ОБА"]["измерения"]["Vps"]["значение"],
            "109 см/сек",
        )
        self.assertEqual(
            sides["справа"]["наблюдения"],
            ["Артерии осмотрены, проходимы"],
        )


if __name__ == "__main__":
    unittest.main()
