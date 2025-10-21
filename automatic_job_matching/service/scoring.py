"""Scoring strategy abstractions for confidence calculation.

Applies SOLID principles:
 - Single Responsibility: Scoring logic isolated from matcher search logic.
 - Open/Closed: New scoring strategies can be added without modifying matchers.
 - Liskov: All scorers share the same interface and are interchangeable.
 - Interface Segregation: Minimal interface (single `score` method) required by matchers.
 - Dependency Inversion: Matchers depend on abstraction (`ConfidenceScorer`) not concrete implementations.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
import difflib


class ConfidenceScorer(ABC):
    """Abstract confidence scorer.

    Implementations must return a float in the inclusive range [0.0, 1.0].
    Inputs should already be normalized (lowercased, trimmed, punctuation handled).
    """

    @abstractmethod
    def score(self, norm_query: str, norm_candidate: str) -> float:  # pragma: no cover - interface
        raise NotImplementedError


class FuzzyConfidenceScorer(ConfidenceScorer):
    """Composite heuristic scorer used for fuzzy name similarity.

    The algorithm combines several similarity signals:
      - Full sequence ratio (difflib)
      - Jaccard token overlap
      - Token coverage (bidirectional containment)
      - Near-token similarity (substring / high per-token ratio)
      - Length balance (token count ratio)
    A mild bonus is applied when both sequence and jaccard are strong.
    
    ENHANCED: Multi-word query bonus for queries with 2+ significant matching words.
    """

    # Weight constants kept as class attributes to allow easy tuning / subclassing
    W_SEQ = 0.35
    W_JACCARD = 0.25
    W_NEAR = 0.15
    W_COVERAGE = 0.15
    W_LEN = 0.10

    BONUS_THRESHOLD_SEQ = 0.75
    BONUS_THRESHOLD_JACCARD = 0.70
    BONUS_MULTIPLIER = 1.05
    
    # Multi-word matching bonus
    MULTI_WORD_BONUS_BASE = 0.20  # Base bonus for matching multiple significant words

    def score(self, norm_query: str, norm_candidate: str) -> float:
        """Compute similarity score in [0,1] with multi-word matching boost."""
        trivial = self._check_trivial(norm_query, norm_candidate)
        if trivial is not None:
            return trivial

        seq = self._sequence_ratio(norm_query, norm_candidate)
        q_tokens, c_tokens = norm_query.split(), norm_candidate.split()
        if not q_tokens or not c_tokens:
            return 0.0

        jaccard, coverage = self._overlap_metrics(q_tokens, c_tokens)
        near = self._near_similarity(q_tokens, c_tokens)
        len_balance = self._length_balance(q_tokens, c_tokens)

        # Base score calculation
        score = (
            seq * self.W_SEQ +
            jaccard * self.W_JACCARD +
            near * self.W_NEAR +
            coverage * self.W_COVERAGE +
            len_balance * self.W_LEN
        )

        # Apply standard bonus for high sequence + jaccard
        if self._eligible_bonus(seq, jaccard):
            score = min(1.0, score * self.BONUS_MULTIPLIER)

        multi_word_bonus = self._calculate_multi_word_bonus(q_tokens, c_tokens)
        if multi_word_bonus > 0:
            score = min(1.0, score + multi_word_bonus)


        return self._clamp(score)

    # ---- Helper methods (extracted to reduce cognitive complexity) ----
    @staticmethod
    def _check_trivial(a: str, b: str) -> float | None:
        if not a or not b:
            return 0.0
        if a == b:
            return 1.0
        return None

    @staticmethod
    def _sequence_ratio(a: str, b: str) -> float:
        return difflib.SequenceMatcher(None, a, b).ratio()

    @staticmethod
    def _overlap_metrics(q_tokens: list[str], c_tokens: list[str]) -> tuple[float, float]:
        q_set, c_set = set(q_tokens), set(c_tokens)
        inter = q_set & c_set
        union = q_set | c_set
        if not union:
            return 0.0, 0.0
        jaccard = len(inter) / len(union)
        coverage = 0.5 * ((len(inter)/len(q_set)) + (len(inter)/len(c_set))) if q_set and c_set else 0.0
        return jaccard, coverage

    @staticmethod
    def _length_balance(q_tokens: list[str], c_tokens: list[str]) -> float:
        return min(len(q_tokens), len(c_tokens)) / max(len(q_tokens), len(c_tokens))

    @staticmethod
    def _token_pair_score(qt: str, ct: str) -> float:
        if len(qt) < 3 or len(ct) < 3:
            return 0.0
        if qt == ct:
            return 1.0
        if qt in ct or ct in qt:
            return 0.8
        r = difflib.SequenceMatcher(None, qt, ct).ratio()
        return 0.6 * r if r >= 0.75 else 0.0

    def _near_similarity(self, q_tokens: list[str], c_tokens: list[str]) -> float:
        total_pairs = 0
        near_hits = 0.0
        for qt in q_tokens:
            for ct in c_tokens:
                pair_score = self._token_pair_score(qt, ct)
                if pair_score:
                    total_pairs += 1
                    near_hits += pair_score
        return near_hits / total_pairs if total_pairs else 0.0

    def _eligible_bonus(self, seq: float, jaccard: float) -> bool:
        return seq >= self.BONUS_THRESHOLD_SEQ and jaccard >= self.BONUS_THRESHOLD_JACCARD

    def _calculate_multi_word_bonus(self, q_tokens: list[str], c_tokens: list[str]) -> float:
        """Calculate bonus for queries with multiple significant words matching.
        
        Logic:
        - Identify significant words (length >= 4, common stop words filtered)
        - Count how many significant query words appear in candidate
        - If 2+ significant words match, apply scaled bonus
        
        Returns:
            Float bonus value (0.0 to MULTI_WORD_BONUS_BASE)
        """
        # Filter to significant words (length >= 4)
        significant_query_words = [w for w in q_tokens if len(w) >= 4]
        
        # Need at least 2 significant words to qualify for bonus
        if len(significant_query_words) < 2:
            return 0.0
        
        c_set = set(c_tokens)
        
        # Count exact matches of significant words
        matched_count = sum(1 for w in significant_query_words if w in c_set)
        
        # Bonus only applies if 2+ significant words matched
        if matched_count < 2:
            return 0.0
        
        # Scale bonus based on match percentage
        # 100% match = full bonus, 50% match = half bonus
        match_ratio = matched_count / len(significant_query_words)
        bonus = self.MULTI_WORD_BONUS_BASE * match_ratio
        
        return bonus

    @staticmethod
    def _clamp(v: float) -> float:
        if v < 0.0:
            return 0.0
        if v > 1.0:
            return 1.0
        return v

class ExactConfidenceScorer(ConfidenceScorer):
    """Scorer for exact matches: full equality -> 1.0 else 0.0.

    This class exists for symmetry and future extension (e.g., degrade for near-code matches).
    """

    def score(self, norm_query: str, norm_candidate: str) -> float:
        if not norm_query or not norm_candidate:
            return 0.0
        return 1.0 if norm_query == norm_candidate else 0.0


class NoOpScorer(ConfidenceScorer):
    """Always returns 0.0 (placeholder / disabling scorer)."""
    def score(self, norm_query: str, norm_candidate: str) -> float:  # pragma: no cover - trivial
        return 0.0


__all__ = [
    "ConfidenceScorer",
    "FuzzyConfidenceScorer",
    "ExactConfidenceScorer",
    "NoOpScorer",
]