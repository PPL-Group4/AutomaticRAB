from __future__ import annotations
from dataclasses import dataclass
from typing import List, Protocol, Optional
import difflib

from automatic_job_matching.utils.text_normalizer import normalize_text

@dataclass
class AhsRow:
    id: int
    code: str
    name: str

class AhsRepository(Protocol):
    def by_code_like(self, code: str) -> List[AhsRow]: ...
    def by_name_candidates(self, head_token: str) -> List[AhsRow]: ...
    def get_all_ahs(self) -> List[AhsRow]: ...

def _norm_name(s: str) -> str:
    return normalize_text(s or "")

class FuzzyMatcher:
    def __init__(self, repo: AhsRepository, min_similarity: float = 0.6):
        self.repo = repo
        self.min_similarity = max(0.0, min(1.0, min_similarity))

    def match(self, description: str) -> Optional[dict]:
        if not description:
            return None

        raw = description.strip()
        
        name_match = self._fuzzy_match_name(raw)
        return name_match

    def _fuzzy_match_name(self, raw_input: str) -> Optional[dict]:
        ndesc = _norm_name(raw_input)
        if not ndesc:
            return None

        head = ndesc.split(" ", 1)[0]
        candidates = self.repo.by_name_candidates(head)
        
        if not candidates:
            candidates = self.repo.get_all_ahs()

        best_match = None
        best_similarity = 0.0

        for cand in candidates:
            cand_name = _norm_name(cand.name)
            if not cand_name:
                continue
                
            ratio = difflib.SequenceMatcher(None, ndesc, cand_name).ratio()
            
            partial_score = self._calculate_partial_similarity(ndesc, cand_name)
            similarity = max(ratio, partial_score)
            
            if similarity >= self.min_similarity and similarity > best_similarity:
                best_similarity = similarity
                best_match = cand

        if best_match:
            return {
                "source": "ahs",
                "id": best_match.id,
                "code": best_match.code,
                "name": best_match.name,
                "matched_on": "name",
            }

        return None

    def _calculate_partial_similarity(self, text1: str, text2: str) -> float:
        if not text1 or not text2:
            return 0.0
            
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        jaccard = len(intersection) / len(union) if union else 0.0
        
        partial_matches = 0
        total_comparisons = 0
        
        for w1 in words1:
            for w2 in words2:
                if len(w1) >= 3 and len(w2) >= 3:  
                    total_comparisons += 1
                    if w1 in w2 or w2 in w1:
                        partial_matches += 1
        
        partial_score = partial_matches / total_comparisons if total_comparisons > 0 else 0.0
        
        return max(jaccard, partial_score * 0.8)

    def find_multiple_matches(self, description: str, limit: int = 5) -> List[dict]:
        """Returns multiple fuzzy name matches sorted by internal similarity"""
        if not description or limit <= 0:
            return []

        raw = description.strip()
        matches = self._get_multiple_name_matches(raw, limit)

        matches.sort(key=lambda x: x.get("_internal_score", 0), reverse=True)
        
        for match in matches:
            match.pop("_internal_score", None)
        
        return matches[:limit]

    def _get_multiple_name_matches(self, raw_input: str, limit: int) -> List[dict]:
        """Get multiple fuzzy name matches"""
        ndesc = _norm_name(raw_input)
        if not ndesc:
            return []

        head = ndesc.split(" ", 1)[0]
        candidates = self.repo.by_name_candidates(head)
        
        if not candidates:
            candidates = self.repo.get_all_ahs()

        matches = []
        for cand in candidates:
            cand_name = _norm_name(cand.name)
            if not cand_name:
                continue
                
            ratio = difflib.SequenceMatcher(None, ndesc, cand_name).ratio()
            partial_score = self._calculate_partial_similarity(ndesc, cand_name)
            similarity = max(ratio, partial_score)
            
            if similarity >= self.min_similarity:
                matches.append({
                    "source": "ahs",
                    "id": cand.id,
                    "code": cand.code,
                    "name": cand.name,
                    "matched_on": "name",
                    "_internal_score": similarity,  
                })

        matches.sort(key=lambda x: x["_internal_score"], reverse=True)
        return matches[:limit]