from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Optional, Set

# Constants for pattern matching
MAX_CODE_PREFIX_LENGTH = 4
MAX_CODE_PARTS = 6
MAX_CODE_PART_LENGTH = 4

# Precompiled regex patterns
_WHITESPACE_PATTERN = re.compile(r"\s+", re.UNICODE)
_NON_ALPHANUMERIC_PATTERN = re.compile(r"[^0-9a-z]+")
_CODE_PATTERN = re.compile(r"\b[A-Za-z]+(?:[.-][A-Za-z0-9]+)+\b")

# Space-separated code patterns
_AT_TWO_PARTS_PATTERN = re.compile(r"\b(AT)\s+(\d+)\s+(\d+)\b", re.IGNORECASE)
_AT_ONE_PART_PATTERN = re.compile(r"\b(AT)\s+(\d+)\b", re.IGNORECASE)
_GENERIC_SPACED_CODE_PATTERN = re.compile(
    rf"\b([A-Za-z]{{1,{MAX_CODE_PREFIX_LENGTH}}})"
    rf"((?:\s+[A-Za-z0-9]{{1,{MAX_CODE_PART_LENGTH}}}){{1,{MAX_CODE_PARTS}}})\b"
)

# Character substitution mappings
_CHARACTER_SUBSTITUTIONS = [
    ("m²", "m2"),
    ("㎡", "m2"),
    ("²", "2"),
    ("m³", "m3"),
    ("㎥", "m3"),
    ("³", "3"),
    ("–", "-"),
    ("—", "-"),
    ("·", " "),
    ("×", "x"),
    ("Ø", " "),
    ("@", " "),
    ("/", " "),
    (":", " "),
    (";", " "),
    (",", " "),
    (".", " "),
    ("!", " "),
    ("?", " "),
    ("(", " "),
    (")", " "),
    ("[", " "),
    ("]", " "),
    ("{", " "),
    ("}", " "),
    ("'", " "),
]

def _strip_diacritics(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_chars = (ch for ch in normalized if not unicodedata.combining(ch))
    return "".join(ascii_chars).encode("ascii", "ignore").decode("ascii")


def _convert_at_codes(text: str) -> str:

    # Handle two-part AT codes: AT 19 1 -> AT.19-1
    text = _AT_TWO_PARTS_PATTERN.sub(
        lambda m: f"{m.group(1)}.{m.group(2)}-{m.group(3)}", text
    )
    # Handle one-part AT codes: AT 20 -> AT.20
    text = _AT_ONE_PART_PATTERN.sub(
        lambda m: f"{m.group(1)}.{m.group(2)}", text
    )
    return text


def _convert_generic_codes(text: str) -> str:
    def _create_dotted_code(match: re.Match[str]) -> str:
        prefix = match.group(1)
        parts = match.group(2).split()

        # Require at least one digit among parts to avoid normal words
        has_digit = any(any(char.isdigit() for char in part) for part in parts)
        if not has_digit:
            return match.group(0)

        return f"{prefix}.{'.'.join(parts)}"

    return _GENERIC_SPACED_CODE_PATTERN.sub(_create_dotted_code, text)


def _protect_codes(text: str) -> tuple[str, dict[str, str]]:
    code_map: dict[str, str] = {}

    def _create_placeholder(match: re.Match[str]) -> str:
        placeholder = f"codeplaceholder{len(code_map)}"
        code_map[placeholder] = match.group(0)
        return f" {placeholder} "

    protected_text = _CODE_PATTERN.sub(_create_placeholder, text)
    return protected_text, code_map


def _apply_character_substitutions(text: str) -> str:
    for old_char, new_char in _CHARACTER_SUBSTITUTIONS:
        text = text.replace(old_char, new_char)
    return text


def _remove_stopwords_from_text(text: str, stopwords: Set[str]) -> str:
    if not stopwords:
        return text
    return " ".join(token for token in text.split() if token not in stopwords)


def _restore_protected_codes(text: str, code_map: dict[str, str]) -> str:
    for placeholder, original_code in code_map.items():
        text = text.replace(placeholder, original_code)
    return text


def normalize_text(
    text: str,
    *,
    remove_stopwords: bool = False,
    stopwords: Optional[Iterable[str]] = None,
) -> str:
    if not text:
        return ""

    normalized_text = _convert_at_codes(text)

    normalized_text, code_map = _protect_codes(normalized_text)

    normalized_text = normalized_text.lower()
    normalized_text = _apply_character_substitutions(normalized_text)
    normalized_text = _strip_diacritics(normalized_text)
    normalized_text = _NON_ALPHANUMERIC_PATTERN.sub(" ", normalized_text)
    normalized_text = _WHITESPACE_PATTERN.sub(" ", normalized_text).strip()

    if not normalized_text:
        return normalized_text

    if remove_stopwords:
        stopword_set = set(stopwords or [])
        normalized_text = _remove_stopwords_from_text(normalized_text, stopword_set)

    normalized_text = _restore_protected_codes(normalized_text, code_map)

    return _WHITESPACE_PATTERN.sub(" ", normalized_text).strip()
