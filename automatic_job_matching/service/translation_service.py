from functools import lru_cache
from threading import Lock

from deep_translator import GoogleTranslator
from langdetect import detect, LangDetectException
from AutomaticRAB.security.input_sanitizer import validate_input_size, validate_content
from AutomaticRAB.security.ssrf import block_ssrf
from AutomaticRAB.security.timeout import run_with_timeout
from requests.exceptions import Timeout

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

        validate_input_size(text)
        validate_content(text)
        block_ssrf(text)

        try:
            lang = detect(text)
        except LangDetectException:
            lang = "unknown"

        if lang == "id":
            return text

        try:
            return run_with_timeout(
                3, 
                self.translator.translate,
                text
            )
        except TimeoutError:
            return "[Translation unavailable: timeout]"
        except Exception:
            return "[Translation failed]"
     
    
