from functools import lru_cache
from threading import Lock

from deep_translator import GoogleTranslator
from langdetect import detect, LangDetectException

_TRANSLATE_CALL_LOCK = Lock()


@lru_cache(maxsize=4096)
def _detect_language(sample: str) -> str:
    try:
        return detect(sample)
    except LangDetectException:
        return "unknown"


def _translate(sample: str) -> str:
    with _TRANSLATE_CALL_LOCK:
        translator = GoogleTranslator(source="en", target="id")
        return translator.translate(sample)


class TranslationService:
    def translate_to_indonesian(self, text: str) -> str:
        if not text:
            return ""

        normalized = text.strip()
        if not normalized:
            return ""

        lang = _detect_language(normalized)
        if lang == "id":
            return normalized

        try:
            return _translate(normalized)
        except Exception:
            return normalized