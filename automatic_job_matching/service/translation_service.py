import logging
from deep_translator import GoogleTranslator

class TranslationService:
    def __init__(self):
        self.translator = GoogleTranslator(source='en', target='id')

    def translate_to_indonesian(self, text: str) -> str:
        if not text:
            return ""
        try:
            return self.translator.translate(text)
        except Exception:
            return text
