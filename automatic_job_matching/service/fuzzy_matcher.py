from __future__ import annotations
from dataclasses import dataclass
from typing import List, Protocol, Optional
import difflib
import logging

from automatic_job_matching.utils.text_normalizer import normalize_text
from automatic_job_matching.service.scoring import ConfidenceScorer, FuzzyConfidenceScorer

logger = logging.getLogger(__name__)

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

# SOLID: Single Responsibility Principle - Only handles similarity calculations
class SimilarityCalculator:
    @staticmethod
    def calculate_sequence_similarity(text1: str, text2: str) -> float:
        score = difflib.SequenceMatcher(None, text1, text2).ratio()

        logger.debug("Seq similarity between %r and %r = %.4f", text1, text2, score)

        return score
    
    @staticmethod
    def calculate_partial_similarity(text1: str, text2: str) -> float:
        if not text1 or not text2:
            return 0.0
            
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        # Calculate Jaccard similarity
        jaccard = SimilarityCalculator._calculate_jaccard_similarity(words1, words2)
        
        # Calculate partial word matching score
        partial_score = SimilarityCalculator._calculate_partial_word_score(words1, words2)
        
        score = max(jaccard, partial_score * 0.8)

        logger.debug("Partial similarity between %r and %r = %.4f", text1, text2, score)

        return score
    
    @staticmethod
    def _calculate_jaccard_similarity(words1: set, words2: set) -> float:
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union) if union else 0.0
    
    @staticmethod
    def _calculate_partial_word_score(words1: set, words2: set) -> float:
        # Filter words with length >= 3 to avoid processing very short words
        filtered_words1 = [w for w in words1 if len(w) >= 3]
        filtered_words2 = [w for w in words2 if len(w) >= 3]
        
        if not filtered_words1 or not filtered_words2:
            return 0.0
        
        partial_matches = sum(
            1 for w1 in filtered_words1 
            for w2 in filtered_words2 
            if w1 in w2 or w2 in w1
        )
        
        total_comparisons = len(filtered_words1) * len(filtered_words2)
        return partial_matches / total_comparisons

# SOLID: Single Responsibility Principle - Only handles candidate retrieval logic
class CandidateProvider:
    def __init__(self, repository: AhsRepository):
        self._repository = repository
    
    def get_candidates_by_head_token(self, normalized_input: str) -> List[AhsRow]:
        logger.debug("CandidateProvider: head_token search for input=%s", normalized_input)

        if not normalized_input:
            return self._repository.get_all_ahs()
        
        head = normalized_input.split(" ", 1)[0]
        candidates = self._repository.by_name_candidates(head)
        
        if not candidates:
            logger.debug("No candidates by head token, falling back to all AHS")
            candidates = self._repository.get_all_ahs()
        
        logger.info("CandidateProvider returned %d candidates", len(candidates))
        return candidates

# SOLID: Open/Closed Principle + Dependency Inversion Principle
# Easy to extend with new matching strategies without modifying existing code
class MatchingProcessor:
    def __init__(self, 
                 similarity_calculator: SimilarityCalculator,
                 candidate_provider: CandidateProvider,
                 min_similarity: float = 0.6):
        self._similarity_calculator = similarity_calculator
        self._candidate_provider = candidate_provider
        self._min_similarity = max(0.0, min(1.0, min_similarity))
    
    def find_best_match(self, query: str) -> Optional[dict]:
        """Find the best matching AHS record."""
        logger.debug("Finding best fuzzy match for query=%s", query)

        normalized_query = _norm_name(query)
        if not normalized_query:
            return None
        
        candidates = self._candidate_provider.get_candidates_by_head_token(normalized_query)
        
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            candidate_name = _norm_name(candidate.name)
            if not candidate_name:
                continue
            
            # Use hybrid approach: max of sequence and partial similarity
            seq_score = self._similarity_calculator.calculate_sequence_similarity(normalized_query, candidate_name)
            partial_score = self._similarity_calculator.calculate_partial_similarity(normalized_query, candidate_name)
            similarity_score = max(seq_score, partial_score)
            
            if similarity_score >= self._min_similarity and similarity_score > best_score:
                best_score = similarity_score
                best_match = {
                    "source": "ahs",
                    "id": candidate.id,
                    "code": candidate.code,
                    "name": candidate.name,
                    "matched_on": "name",
                }
        
        logger.info("Best fuzzy match score=%.4f", best_score)
        return best_match
    
    def find_multiple_matches(self, query: str, limit: int = 5) -> List[dict]:
        """Find multiple matching AHS records sorted by similarity."""
        logger.debug("Finding up to %d fuzzy matches for query=%s", limit, query)

        if limit <= 0:
            return []
            
        normalized_query = _norm_name(query)
        if not normalized_query:
            return []
        
        candidates = self._candidate_provider.get_candidates_by_head_token(normalized_query)
        matches = []
        
        for candidate in candidates:
            candidate_name = _norm_name(candidate.name)
            if not candidate_name:
                continue
            
            seq_score = self._similarity_calculator.calculate_sequence_similarity(normalized_query, candidate_name)
            partial_score = self._similarity_calculator.calculate_partial_similarity(normalized_query, candidate_name)
            similarity_score = max(seq_score, partial_score)
            
            if similarity_score >= self._min_similarity:
                match_result = {
                    "source": "ahs",
                    "id": candidate.id,
                    "code": candidate.code,
                    "name": candidate.name,
                    "matched_on": "name",
                    "_internal_score": similarity_score
                }
                matches.append((similarity_score, match_result))
        
        # Sort by similarity score (descending)
        matches.sort(key=lambda x: x[0], reverse=True)
        
        logger.info("Multiple fuzzy matches found=%d", len(matches))
        return [match[1] for match in matches[:limit]]

# SOLID: Dependency Inversion Principle - Main class depends on abstractions
class FuzzyMatcher:
    def __init__(self, repo: AhsRepository, min_similarity: float = 0.6, scorer: ConfidenceScorer | None = None):
        """Fuzzy matcher with injected dependencies."""
        self.repo = repo
        self.min_similarity = max(0.0, min(1.0, min_similarity))
        self.scorer: ConfidenceScorer = scorer or FuzzyConfidenceScorer()
        
        # Inject dependencies instead of creating them internally
        self._similarity_calculator = SimilarityCalculator()
        self._candidate_provider = CandidateProvider(repo)
        self._matching_processor = MatchingProcessor(
            self._similarity_calculator,
            self._candidate_provider,
            min_similarity
        )

    def match(self, description: str) -> Optional[dict]:
        """Main entry point for single match."""
        logger.debug("FuzzyMatcher.match called with description=%r", description)

        if not description:
            return None
        
        return self._matching_processor.find_best_match(description.strip())

    def find_multiple_matches(self, description: str, limit: int = 5) -> List[dict]:
        """Main entry point for multiple matches."""
        logger.debug("FuzzyMatcher.find_multiple_matches called with description=%r", description)

        if not description or limit <= 0:
            return []
        
        return self._matching_processor.find_multiple_matches(description.strip(), limit)

    # Confidence scoring methods
    def match_with_confidence(self, description: str) -> Optional[dict]:
        """Return single best match including a confidence score."""
        logger.debug("FuzzyMatcher.match_with_confidence called with description=%r", description)

        if not description:
            return None
        
        normalized_query = _norm_name(description.strip())
        if not normalized_query:
            return None

        candidates = self._candidate_provider.get_candidates_by_head_token(normalized_query)
        
        best = None
        best_conf = 0.0
        for cand in candidates:
            norm_cand = _norm_name(cand.name)
            if not norm_cand:
                continue
            conf = self.scorer.score(normalized_query, norm_cand)
            logger.debug("Confidence score vs candidate %r = %.4f", cand.name, conf)
            if conf >= self.min_similarity and conf > best_conf:
                best_conf = conf
                best = cand

        if best:
            logger.info("Best confidence match id=%s score=%.4f", best.id, best_conf)
            return {
                "source": "ahs",
                "id": best.id,
                "code": best.code,
                "name": best.name,
                "matched_on": "name",
                "confidence": round(best_conf, 4)
            }
        logger.info("No confident match found for query=%r", description)
        return None

    def find_multiple_matches_with_confidence(self, description: str, limit: int = 5) -> List[dict]:
        """Return multiple matches each with confidence score, sorted desc."""
        logger.debug("FuzzyMatcher.find_multiple_matches_with_confidence called (limit=%d) desc=%r", limit, description)
        
        if not description or limit <= 0:
            return []
        
        normalized_query = _norm_name(description.strip())
        if not normalized_query:
            return []
            
        candidates = self._candidate_provider.get_candidates_by_head_token(normalized_query)

        results = []
        for cand in candidates:
            norm_cand = _norm_name(cand.name)
            if not norm_cand:
                continue
            conf = self.scorer.score(normalized_query, norm_cand)
            logger.debug("Confidence score vs candidate %r = %.4f", cand.name, conf)
            if conf >= self.min_similarity:
                results.append((conf, {
                    "source": "ahs",
                    "id": cand.id,
                    "code": cand.code,
                    "name": cand.name,
                    "matched_on": "name",
                    "confidence": round(conf, 4)
                }))
        
        results.sort(key=lambda x: x[0], reverse=True)

        logger.info("Found %d matches with confidence >= %.2f", len(results), self.min_similarity)
        return [result[1] for result in results[:limit]]

    # Backward compatibility methods
    def _calculate_partial_similarity(self, text1: str, text2: str) -> float:
        """Backward compatibility wrapper."""
        logger.debug("Backward partial similarity between %r and %r", text1, text2)
        return self._similarity_calculator.calculate_partial_similarity(text1, text2)

    def _calculate_confidence_score(self, norm_query: str, norm_candidate: str) -> float:
        """Backward-compatible delegate to injected scorer."""
        logger.debug("Backward confidence score between %r and %r", norm_query, norm_candidate)
        return self.scorer.score(norm_query, norm_candidate)

    # Legacy methods for backward compatibility
    def _fuzzy_match_name(self, raw_input: str) -> Optional[dict]:
        logger.debug("Legacy _fuzzy_match_name called with input=%r", raw_input)
        return self.match(raw_input)

    def _get_multiple_name_matches(self, raw_input: str, limit: int) -> List[dict]:
        logger.debug("Legacy _get_multiple_name_matches called with input=%r limit=%d",
                     raw_input, limit)
        return self.find_multiple_matches(raw_input, limit)

    def _fuzzy_match_name_with_confidence(self, raw_input: str) -> Optional[dict]:
       logger.debug("Legacy _fuzzy_match_name_with_confidence called with input=%r", raw_input)
       return self.match_with_confidence(raw_input)

    def _get_multiple_name_matches_with_confidence(self, raw_input: str, limit: int) -> List[dict]:
        logger.debug("Legacy _get_multiple_name_matches_with_confidence called with input=%r limit=%d",
                     raw_input, limit)
        return self.find_multiple_matches_with_confidence(raw_input, limit)