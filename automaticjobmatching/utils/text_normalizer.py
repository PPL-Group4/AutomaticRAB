"""
Text normalization utilities for Indonesian/English construction domain terms.

normalize_text(text: str, *, remove_stopwords: bool = False, stopwords: set[str] | None = None) -> str
- Lowercase
- Replace common unicode symbols (e.g., m² -> m2, en/em dash -> space)
- Strip diacritics to ASCII
- Remove punctuation/symbols except alphanumerics and spaces
- Collapse all whitespace to single spaces and trim ends
- Optionally remove stopwords (exact token match)
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Optional, Set

# Precompile patterns
_WS_RE = re.compile(r"\s+", re.UNICODE)
# Keep letters and digits; everything else becomes space
_NON_ALNUM_RE = re.compile(r"[^0-9a-z]+")

_PRE_SUBS = [
    ("m²", "m2"),
    ("㎡", "m2"),
    ("²", "2"),
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
]


def _strip_diacritics(s: str) -> str:
    # Normalize to NFKD, then remove combining marks
    normalized = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).encode("ascii", "ignore").decode("ascii")


def normalize_text(
    text: str,
    *,
    remove_stopwords: bool = False,
    stopwords: Optional[Iterable[str]] = None,
) -> str:
    if text is None:
        return ""

    s = text.lower()

    # Pre substitutions for units/symbols we care about
    for old, new in _PRE_SUBS:
        s = s.replace(old, new)

    # Strip diacritics
    s = _strip_diacritics(s)

    # Replace anything non-alphanumeric with spaces
    s = _NON_ALNUM_RE.sub(" ", s)

    # Collapse whitespace
    s = _WS_RE.sub(" ", s).strip()

    if not s:
        return s

    if remove_stopwords:
        sw: Set[str] = set(stopwords or [])
        if sw:
            tokens = [tok for tok in s.split(" ") if tok and tok not in sw]
            s = " ".join(tokens)

    return s
