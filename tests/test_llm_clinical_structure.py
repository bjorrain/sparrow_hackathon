import json
import unittest
from unittest.mock import Mock, patch

from sparrow.backend.parsers.llm_clinical_structure import (
    LLMClinicalStructureParser,
)


class LLMClinicalStructureParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = LLMClinicalStructureParser(
            base_url="https://llm.example/v1/",
            model="medical-model",
            api_key="test-key",
        )

    @patch("sparrow.backend.parsers.llm_clinical_structure.requests.post")
    def test_sends_chat_request_and_returns_matching_structure(
        self, post: Mock
    ) -> None:
        expected = {
            "structures": [
                {
                    "name": "печень",
                    "size": "145 мм",
                    "morphology": {"структура": "однородная"},
                    "status": "норма",
                }
            ],
            "technical_data": {"тип_исследования": "УЗИ ОБП"},
            "conclusion": {"text": "Без патологии", "recommendations": None},
        }
        response = Mock()
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": (
                            "```json\n"
                            f"{json.dumps(expected, ensure_ascii=False)}\n"
                            "```"
                        )
                    }
                }
            ]
        }
        post.return_value = response

        result = self.parser.parse("Описание\nПЕЧЕНЬ\nРазмеры в норме")

        self.assertEqual(result, expected)
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://llm.example/v1/chat/completions")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(kwargs["json"]["model"], "medical-model")
        self.assertEqual(kwargs["json"]["temperature"], 0)
        self.assertEqual(
            kwargs["json"]["messages"][1]["content"],
            "Описание\nПЕЧЕНЬ\nРазмеры в норме",
        )
        response.raise_for_status.assert_called_once()

    @patch("sparrow.backend.parsers.llm_clinical_structure.requests.post")
    def test_rejects_invalid_response_shape(self, post: Mock) -> None:
        response = Mock()
        response.json.return_value = {
            "choices": [{"message": {"content": '{"structures": {}}'}}]
        }
        post.return_value = response

        with self.assertRaisesRegex(ValueError, "Неверные ключи"):
            self.parser.parse("Протокол")

    @patch("sparrow.backend.parsers.llm_clinical_structure.requests.post")
    def test_rejects_malformed_json(self, post: Mock) -> None:
        response = Mock()
        response.json.return_value = {
            "choices": [{"message": {"content": "не JSON"}}]
        }
        post.return_value = response

        with self.assertRaisesRegex(ValueError, "некорректный JSON"):
            self.parser.parse("Протокол")

    def test_rejects_blank_input_without_api_call(self) -> None:
        with patch(
            "sparrow.backend.parsers.llm_clinical_structure.requests.post"
        ) as post:
            with self.assertRaisesRegex(ValueError, "не должен быть пустым"):
                self.parser.parse(" \n ")
            post.assert_not_called()

    def test_reads_configuration_from_environment(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "OPENAI_BASE_URL": "http://localhost:1234/v1",
                "OPENAI_MODEL": "local-model",
                "OPENAI_API_KEY": "local-key",
            },
            clear=True,
        ):
            parser = LLMClinicalStructureParser.from_env()

        self.assertEqual(parser._base_url, "http://localhost:1234/v1")
        self.assertEqual(parser._model, "local-model")
        self.assertEqual(parser._api_key, "local-key")


if __name__ == "__main__":
    unittest.main()
