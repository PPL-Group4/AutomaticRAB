import logging

from automatic_job_matching.repository.ahs_repo import DbAhsRepository
from automatic_job_matching.service.exact_matcher import ExactMatcher
from automatic_job_matching.service.fuzzy_matcher import FuzzyMatcher
from automatic_job_matching.service.scoring import FuzzyConfidenceScorer
from automatic_price_matching.fallback_validator import apply_fallback
logger = logging.getLogger(__name__)

class MatchingService:
    @staticmethod
    def perform_exact_match(description):
        logger.info("perform_exact_match called (len=%d)", len(description))

        matcher = ExactMatcher(DbAhsRepository())
        result = matcher.match(description)

        logger.debug("Exact match result: %s", result)
        return result

    @staticmethod
    def perform_fuzzy_match(description, min_similarity=0.6):
        logger.info("perform_fuzzy_match called (len=%d, min_similarity=%.2f)",
                    len(description), min_similarity)
        
        matcher = FuzzyMatcher(DbAhsRepository(), min_similarity, scorer=FuzzyConfidenceScorer())
        confidence_result = getattr(matcher, 'match_with_confidence', None)
        if callable(confidence_result):
            result = confidence_result(description)
        else:
            result = matcher.match(description)

        logger.debug("Fuzzy match result: %s", result)
        return result
    
    @staticmethod
    def perform_multiple_match(description, limit=5, min_similarity=0.6):
        logger.info("perform_multiple_match called (len=%d, limit=%d, min_similarity=%.2f)",
                    len(description), limit, min_similarity)
        
        matcher = FuzzyMatcher(DbAhsRepository(), min_similarity, scorer=FuzzyConfidenceScorer())
        confidence_multi = getattr(matcher, 'find_multiple_matches_with_confidence', None)
        
        if callable(confidence_multi):
            results = confidence_multi(description, limit)
        else:
            results = matcher.find_multiple_matches(description, limit)
            
        logger.debug("Multiple fuzzy match results count=%d", len(results))
        return results

    @staticmethod
    def perform_best_match(description: str):
        logger.info("perform_best_match called (len=%d)", len(description))

        min_similarity_single = 0.6
        min_similarity_multiple = 0.4
        limit = 5

        # 1️⃣ Try exact
        result = MatchingService.perform_exact_match(description)

        # 2️⃣ Try fuzzy
        if not result:
            result = MatchingService.perform_fuzzy_match(description, min_similarity_single)

        # 3️⃣ Try multiple fuzzy matches
        if not result:
            result = MatchingService.perform_multiple_match(description, limit, min_similarity_multiple)

        # 4️⃣ Fallback rule
        if not result:
            logger.warning("No AHSP match found for: %s", description)
            result = apply_fallback(description)

        return result