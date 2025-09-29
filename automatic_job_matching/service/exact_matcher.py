from __future__ import annotations
from dataclasses import dataclass
from typing import List, Protocol, Optional

from automatic_job_matching.utils.text_normalizer import normalize_text

@dataclass
class AhsRow:
    id: int
    code: str
    name: str

class AhsRepository(Protocol):
    def by_code_like(self, code: str) -> List[AhsRow]: ...
    def by_name_candidates(self, head_token: str) -> List[AhsRow]: ...

def _norm_code(s: str) -> str:
    s = (s or "").upper()
    return "".join(ch for ch in s if ch.isalnum())

def _norm_name(s: str) -> str:
    return normalize_text(s or "")

class ExactMatcher:
    def __init__(self, repo: AhsRepository):
        self.repo = repo

    def match(self, description: str) -> Optional[dict]:
        if not description:
            return None

        raw = description.strip()
        ncode = _norm_code(raw)
        looks_like_code = any(ch.isalpha() for ch in raw) and any(ch.isdigit() for ch in raw) and len(ncode) >= 3
        if looks_like_code:
            for cand in self.repo.by_code_like(raw):
                if _norm_code(cand.code) == ncode:
                    return {
                        "source": "ahs",
                        "id": cand.id,
                        "code": cand.code,
                        "name": cand.name,
                        "confidence": 1.0,
                        "matched_on": "code",
                    }

        ndesc = _norm_name(description)
        if not ndesc:
            return None

        head = ndesc.split(" ", 1)[0]
        for cand in self.repo.by_name_candidates(head):
            if _norm_name(cand.name) == ndesc:
                return {
                    "source": "ahs",
                    "id": cand.id,
                    "code": cand.code,
                    "name": cand.name,
                    "confidence": 1.0,
                    "matched_on": "name",
                }

        return None
