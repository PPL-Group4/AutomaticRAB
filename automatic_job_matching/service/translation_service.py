import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from functools import lru_cache
from threading import Lock
from typing import Iterable
from urllib.parse import urlparse

from deep_translator import GoogleTranslator
from langdetect import detect, LangDetectException

import ipaddress

_TRANSLATE_CALL_LOCK = Lock()
_BASE64_LIKE_PATTERN = re.compile(r"^[A-Za-z0-9+/=]+$")
_URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_SQL_KEYWORDS: Iterable[str] = (
    "drop table",
    "union select",
    "insert into",
    "update ",
    "delete from",
    "--",
    ";--",
)

MAX_TEXT_LENGTH = 4096
TRANSLATION_TIMEOUT_SECONDS = 5.0


@lru_cache(maxsize=4096)
def _detect_language(sample: str) -> str:
    try:
        return detect(sample)
    except LangDetectException:
        return "unknown"


def _is_base64_like(sample: str) -> bool:
    if len(sample) < 48:
        return False
    if not _BASE64_LIKE_PATTERN.fullmatch(sample):
        return False
    return len(sample) % 4 == 0


def _contains_sql_payload(sample: str) -> bool:
    lowered = sample.lower()
    return any(keyword in lowered for keyword in _SQL_KEYWORDS)


def _extract_urls(sample: str) -> Iterable[str]:
    return _URL_PATTERN.findall(sample)


def _is_blocked_host(host: str) -> bool:
    normalized = host.strip().lower()
    if normalized in {"localhost", "127.0.0.1", "::1"}:
        return True

    try:
        ip = ipaddress.ip_address(normalized)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        # Host is not an IP string; block obvious internal domains
        return normalized.endswith(".local") or normalized.endswith(".internal")


def _validate_no_blocked_urls(sample: str) -> None:
    for match in _extract_urls(sample):
        parsed = urlparse(match)
        if parsed.hostname and _is_blocked_host(parsed.hostname):
            raise ValueError("Blocked URL host")


class TranslationService:
    def __init__(self, source_lang: str = "auto", target_lang: str = "id", timeout_seconds: float = TRANSLATION_TIMEOUT_SECONDS):
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.timeout_seconds = timeout_seconds
        self.translator = self._create_translator()

    def _create_translator(self) -> GoogleTranslator:
        return GoogleTranslator(source=self.source_lang, target=self.target_lang)

    def _validate_input(self, text: str) -> str:
        if not text:
            return ""

        normalized = text.strip()
        if not normalized:
            return ""

        if len(normalized) > MAX_TEXT_LENGTH:
            raise ValueError("Input text exceeds allowed length")

        _validate_no_blocked_urls(normalized)

        if _contains_sql_payload(normalized):
            raise ValueError("SQL-like payloads are not allowed")

        if _is_base64_like(normalized):
            raise ValueError("Malformed or encoded input not allowed")

        return normalized

    def _translate_with_timeout(self, text: str) -> str:
        def _translate_call(payload: str) -> str:
            with _TRANSLATE_CALL_LOCK:
                return self.translator.translate(payload)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_translate_call, text)
            return future.result(timeout=self.timeout_seconds)

    def translate_to_indonesian(self, text: str) -> str:
        normalized = self._validate_input(text)
        if normalized == "":
            return ""

        lang = _detect_language(normalized)
        if lang == "id":
            return normalized

        try:
            return self._translate_with_timeout(normalized)
        except FuturesTimeoutError:
            return "translation timeout"
        except Exception:
            return normalized