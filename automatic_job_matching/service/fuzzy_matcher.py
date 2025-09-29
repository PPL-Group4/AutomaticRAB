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

    # --- Confidence Scoring Public API ---
    def match_with_confidence(self, description: str) -> Optional[dict]:
        """Return single best match including a confidence score."""
        if not description:
            return None
        raw = description.strip()
        return self._fuzzy_match_name_with_confidence(raw)

    def find_multiple_matches_with_confidence(self, description: str, limit: int = 5) -> List[dict]:
        """Return multiple matches each with confidence score, sorted desc."""
        if not description or limit <= 0:
            return []
        raw = description.strip()
        matches = self._get_multiple_name_matches_with_confidence(raw, limit)
        matches.sort(key=lambda m: m['confidence'], reverse=True)
        return matches[:limit]

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

    # --- Confidence Calculation ---
    def _calculate_confidence_score(self, norm_query: str, norm_candidate: str) -> float:
        """Composite confidence score (0..1) using multiple similarity signals."""
        if not norm_query or not norm_candidate:
            return 0.0

        if norm_query == norm_candidate:
            return 1.0

        # Sequence similarity
        seq = difflib.SequenceMatcher(None, norm_query, norm_candidate).ratio()

        # Token sets
        q_tokens = norm_query.split()
        c_tokens = norm_candidate.split()
        if not q_tokens or not c_tokens:
            return 0.0
        q_set, c_set = set(q_tokens), set(c_tokens)
        inter = q_set & c_set
        union = q_set | c_set
        jaccard = len(inter) / len(union) if union else 0.0

        # Coverage of each side
        coverage = 0.5 * ((len(inter)/len(q_set)) + (len(inter)/len(c_set))) if q_set and c_set else 0.0

        # Substring / near-word similarity
        near_hits = 0.0
        total_pairs = 0
        for qt in q_tokens:
            for ct in c_tokens:
                if len(qt) < 3 or len(ct) < 3:
                    continue
                total_pairs += 1
                if qt == ct:
                    near_hits += 1.0
                elif qt in ct or ct in qt:
                    near_hits += 0.8
                else:
                    r = difflib.SequenceMatcher(None, qt, ct).ratio()
                    if r >= 0.75:
                        near_hits += 0.6 * r
        near = near_hits / total_pairs if total_pairs else 0.0

        # Length balance (number of tokens)
        len_balance = min(len(q_tokens), len(c_tokens)) / max(len(q_tokens), len(c_tokens))

        score = (
            seq * 0.35 +
            jaccard * 0.25 +
            near * 0.15 +
            coverage * 0.15 +
            len_balance * 0.10
        )

        # Mild bonus for strong agreement between seq & jaccard
        if seq >= 0.75 and jaccard >= 0.7:
            score = min(1.0, score * 1.05)

        return max(0.0, min(1.0, score))

    # --- Confidence-enabled internal matching ---
    def _fuzzy_match_name_with_confidence(self, raw_input: str) -> Optional[dict]:
        norm_query = _norm_name(raw_input)
        if not norm_query:
            return None

        head = norm_query.split(" ", 1)[0]
        candidates = self.repo.by_name_candidates(head)
        if not candidates:
            candidates = self.repo.get_all_ahs()

        best = None
        best_conf = 0.0
        for cand in candidates:
            norm_cand = _norm_name(cand.name)
            if not norm_cand:
                continue
            conf = self._calculate_confidence_score(norm_query, norm_cand)
            if conf >= self.min_similarity and conf > best_conf:
                best_conf = conf
                best = cand

        if best:
            return {
                "source": "ahs",
                "id": best.id,
                "code": best.code,
                "name": best.name,
                "matched_on": "name",
                "confidence": round(best_conf, 4)
            }
        return None

    def _get_multiple_name_matches_with_confidence(self, raw_input: str, limit: int) -> List[dict]:
        norm_query = _norm_name(raw_input)
        if not norm_query:
            return []
        head = norm_query.split(" ", 1)[0]
        candidates = self.repo.by_name_candidates(head)
        if not candidates:
            candidates = self.repo.get_all_ahs()

        results: List[dict] = []
        for cand in candidates:
            norm_cand = _norm_name(cand.name)
            if not norm_cand:
                continue
            conf = self._calculate_confidence_score(norm_query, norm_cand)
            if conf >= self.min_similarity:
                results.append({
                    "source": "ahs",
                    "id": cand.id,
                    "code": cand.code,
                    "name": cand.name,
                    "matched_on": "name",
                    "confidence": round(conf, 4)
                })
        results.sort(key=lambda m: m['confidence'], reverse=True)
        return results[:limit]

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