from deep_translator import GoogleTranslator
from langdetect import detect, LangDetectException
from functools import lru_cache

class TranslationService:
    def __init__(self):
        self.translator = GoogleTranslator(source='en', target='id')

    @lru_cache(maxsize=1024)
    def translate_to_indonesian(self, text: str) -> str:
        if not text:
            return ""

        try:
            try:
                lang = detect(text)
            except LangDetectException:
                lang = "unknown"

            if lang == "id":
                return text

            return self.translator.translate(text)
        except Exception:
            return text
