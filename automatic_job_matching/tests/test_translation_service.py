from django.test import SimpleTestCase
from unittest.mock import patch

from automatic_job_matching.service.translation_service import TranslationService
from automatic_job_matching.service.translation_service import LangDetectException


class TranslationServiceTests(SimpleTestCase):
    @patch("automatic_job_matching.service.translation_service.GoogleTranslator")
    def test_translate_to_indonesian_success(self, mock_translator_cls):
        mock_translator = mock_translator_cls.return_value
        mock_translator.translate.return_value = "pasang lantai beton"

        service = TranslationService()
        result = service.translate_to_indonesian("install concrete floor")

        self.assertEqual(result, "pasang lantai beton")
        mock_translator.translate.assert_called_once_with("install concrete floor")

    @patch("automatic_job_matching.service.translation_service.GoogleTranslator")
    def test_translate_to_indonesian_returns_original_on_failure(self, mock_translator_cls):
        mock_translator = mock_translator_cls.return_value
        mock_translator.translate.side_effect = Exception("Network error")

        service = TranslationService()
        result = service.translate_to_indonesian("install concrete floor")

        self.assertEqual(result, "install concrete floor")

    def test_translate_to_indonesian_empty_text(self):
        service = TranslationService()
        result = service.translate_to_indonesian("")
        self.assertEqual(result, "")

    @patch("automatic_job_matching.service.translation_service.detect")
    def test_translate_to_indonesian_skips_when_already_indonesian(self, mock_detect):
        mock_detect.return_value = "id"

        service = TranslationService()
        result = service.translate_to_indonesian("pasang lantai beton")

        self.assertEqual(result, "pasang lantai beton")

    @patch("automatic_job_matching.service.translation_service.GoogleTranslator")
    @patch("automatic_job_matching.service.translation_service.detect")
    def test_translate_to_indonesian_uses_unknown_language_on_detection_error(self, mock_detect, mock_translator_cls):
        mock_detect.side_effect = LangDetectException(0, "detection failure")
        mock_translator = mock_translator_cls.return_value
        mock_translator.translate.return_value = "hasil terjemahan"

        service = TranslationService()
        result = service.translate_to_indonesian("install concrete floor")

        self.assertEqual(result, "hasil terjemahan")
        mock_translator.translate.assert_called_once_with("install concrete floor")
