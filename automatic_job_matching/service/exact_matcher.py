from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Protocol

from automatic_job_matching.utils.text_normalizer import normalize_text

logger = logging.getLogger(__name__)

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
        logger.debug("ExactMatcher.match called with description=%r", description)
        if not description:
            logger.warning("Empty description received")
            return None

        raw = description.strip()
        ncode = _norm_code(raw)
        looks_like_code = any(ch.isalpha() for ch in raw) and any(ch.isdigit() for ch in raw) and len(ncode) >= 3
        logger.debug("Normalized code=%s, looks_like_code=%s", ncode, looks_like_code)

        if looks_like_code:
            for cand in self.repo.by_code_like(raw):
                logger.debug("Checking candidate code=%s", cand.code)
                if _norm_code(cand.code) == ncode:
                    logger.info("Exact code match found: id=%s", cand.id)
                    return {
                        "source": "ahs",
                        "id": cand.id,
                        "code": cand.code,
                        "name": cand.name,
                        "confidence": 1.0,
                        "matched_on": "code",
                    }

        candidates = self.repo.by_name_candidates(description)

        for cand in candidates:
            if _norm_name(cand.name) == _norm_name(description):
                return {
                    "source": "ahs",
                    "id": cand.id,
                    "code": cand.code,
                    "name": cand.name,
                    "confidence": 1.0,
                    "matched_on": "name",
                }

        logger.info("No exact match found for description=%r", description)
        return None
