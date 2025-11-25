import re
from functools import lru_cache

class AbbreviationService:
    MAP = {
        "plst": "plester",
        "smn": "semen",
        "bt": "batu",
        "bkk": "bata kokoh",
        # add more later
    }

    @classmethod
    @lru_cache(maxsize=1024)
    def expand(cls, text: str) -> str:
        if not text:
            return text

        s = text.lower()

        for abbr in sorted(cls.MAP.keys(), key=len, reverse=True):
            full = cls.MAP[abbr]
            if " " in abbr:
                s = s.replace(abbr, full)
            else:
                s = re.sub(rf"\b{re.escape(abbr)}\b", full, s)

        return s
