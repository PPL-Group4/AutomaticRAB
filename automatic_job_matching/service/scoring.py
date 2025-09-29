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
from typing import Protocol


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

    def score(self, norm_query: str, norm_candidate: str) -> float:
        if not norm_query or not norm_candidate:
            return 0.0

        if norm_query == norm_candidate:
            return 1.0

        seq = difflib.SequenceMatcher(None, norm_query, norm_candidate).ratio()

        q_tokens = norm_query.split()
        c_tokens = norm_candidate.split()
        if not q_tokens or not c_tokens:
            return 0.0

        q_set, c_set = set(q_tokens), set(c_tokens)
        inter = q_set & c_set
        union = q_set | c_set
        jaccard = len(inter) / len(union) if union else 0.0

        coverage = 0.5 * ((len(inter)/len(q_set)) + (len(inter)/len(c_set))) if q_set and c_set else 0.0

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

        len_balance = min(len(q_tokens), len(c_tokens)) / max(len(q_tokens), len(c_tokens))

        score = (
            seq * self.W_SEQ +
            jaccard * self.W_JACCARD +
            near * self.W_NEAR +
            coverage * self.W_COVERAGE +
            len_balance * self.W_LEN
        )

        if seq >= self.BONUS_THRESHOLD_SEQ and jaccard >= self.BONUS_THRESHOLD_JACCARD:
            score = min(1.0, score * self.BONUS_MULTIPLIER)

        # Clamp
        if score < 0.0:
            return 0.0
        if score > 1.0:
            return 1.0
        return score


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
