import re

_ROMAN_NUMERAL_PREFIX = re.compile(r"^(?:[0-9]+|[ivxlcdm]+)\s+", re.IGNORECASE)

class NameNormaliser:
    def normalise(self, name: str | None) -> str:
        if not name:
            return ""
        text = re.sub(r"[^0-9a-zA-Z]+", " ", name).strip().lower()
        text = _ROMAN_NUMERAL_PREFIX.sub("", text)
        return re.sub(r"\s+", " ", text)
