from __future__ import annotations

"""Normalization utilities for price matching domain."""

def canonicalize_job_code(code: object) -> str:
    """Return a canonical AHSP job code.

    - Non-strings -> ""
    - Trim whitespace
    - Uppercase letters
    - Treat dash, space, slash, underscore as separators (-> '.')
    - Collapse repeated separators
    - Strip leading/trailing separators
    """
    if not isinstance(code, str):
        return ""

    text = code.strip().upper()
    if not text:
        return ""

    unified = (
        text.replace("-", ".")
        .replace(" ", ".")
        .replace("/", ".")
        .replace("_", ".")
    )
    while ".." in unified:
        unified = unified.replace("..", ".")
    return unified.strip(".")
