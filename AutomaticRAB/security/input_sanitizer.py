import re

MAX_TRANSLATION_LENGTH = 5000  # Google safe recommended max

def validate_input_size(text: str):
    if len(text) > MAX_TRANSLATION_LENGTH:
        raise ValueError("Input too large for translation")

DANGEROUS_PATTERNS = [
    r"SELECT .* FROM",
    r"INSERT INTO",
    r"DROP TABLE",
    r"\{.*\}",                 # huge JSON blobs
    r"[A-Za-z0-9+/=]{500,}",   # base64 dump
]

def validate_content(text: str):
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            raise ValueError("Input appears unsafe or malformed")
