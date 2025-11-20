from functools import lru_cache
from threading import Lock

from deep_translator import GoogleTranslator
from langdetect import detect, LangDetectException

_TRANSLATOR = None
_TRANSLATOR_INIT_LOCK = Lock()
_TRANSLATE_CALL_LOCK = Lock()


def _get_translator() -> GoogleTranslator:
    global _TRANSLATOR
    if _TRANSLATOR is None:
        with _TRANSLATOR_INIT_LOCK:
            if _TRANSLATOR is None:
                _TRANSLATOR = GoogleTranslator(source="en", target="id")
    return _TRANSLATOR


@lru_cache(maxsize=4096)
def _detect_language(sample: str) -> str:
    try:
        return detect(sample)
    except LangDetectException:
        return "unknown"


@lru_cache(maxsize=2048)
def _translate_cached(sample: str) -> str:
    with _TRANSLATE_CALL_LOCK:
        return _get_translator().translate(sample)


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
            return _translate_cached(normalized)
        except Exception:
            return normalized
