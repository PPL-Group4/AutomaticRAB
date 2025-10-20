import logging

from automatic_job_matching.repository.ahs_repo import DbAhsRepository
from automatic_job_matching.service.exact_matcher import ExactMatcher
from automatic_job_matching.service.fuzzy_matcher import FuzzyMatcher
from automatic_job_matching.service.scoring import FuzzyConfidenceScorer
from automatic_job_matching.utils.text_normalizer import normalize_text
from automatic_job_matching.service.translation_service import TranslationService
from automatic_job_matching.service.abbreviation_service import AbbreviationService


logger = logging.getLogger(__name__)

class MatchingService:
    translator = TranslationService()
    
    @staticmethod
    def perform_exact_match(description):
        logger.info("perform_exact_match called (len=%d)", len(description))

        try:
            matcher = ExactMatcher(DbAhsRepository())
            result = matcher.match(description)
            logger.debug("Exact match result: %s", result)
            return result
        except Exception as e:
            logger.error("Error in perform_exact_match: %s", str(e), exc_info=True)
            return None

    @staticmethod
    def perform_fuzzy_match(description, min_similarity=0.6):
        logger.info("perform_fuzzy_match called (len=%d, min_similarity=%.2f)",
                    len(description), min_similarity)
        
        try:
            matcher = FuzzyMatcher(DbAhsRepository(), min_similarity, scorer=FuzzyConfidenceScorer())
            confidence_result = getattr(matcher, 'match_with_confidence', None)
            if callable(confidence_result):
                result = confidence_result(description)
            else:
                result = matcher.match(description)

            logger.debug("Fuzzy match result: %s", result)
            return result
        except Exception as e:
            logger.error("Error in perform_fuzzy_match: %s", str(e), exc_info=True)
            return None
    
    @staticmethod
    def perform_multiple_match(description, limit=5, min_similarity=0.6):
        logger.info("perform_multiple_match called (len=%d, limit=%d, min_similarity=%.2f)",
                    len(description), limit, min_similarity)
        
        try:
            matcher = FuzzyMatcher(DbAhsRepository(), min_similarity, scorer=FuzzyConfidenceScorer())
            confidence_multi = getattr(matcher, 'find_multiple_matches_with_confidence', None)
            
            if callable(confidence_multi):
                results = confidence_multi(description, limit)
            else:
                results = matcher.find_multiple_matches(description, limit)
                
            logger.debug("Multiple fuzzy match results count=%d", len(results))
            return results
        except Exception as e:
            logger.error("Error in perform_multiple_match: %s", str(e), exc_info=True)
            return []
    
    @staticmethod
    def perform_best_match(description: str):
        logger.info("perform_best_match called (len=%d)", len(description))

        translated_text = MatchingService.translator.translate_to_indonesian(description)
        description = translated_text or description
        description = AbbreviationService.expand(description)
        
        try:
            # Adaptive thresholds based on query complexity
            normalized = normalize_text(description)
            
            # Early return for empty/whitespace queries
            if not normalized or not normalized.strip():
                logger.warning("Empty or whitespace-only query, returning None")
                return None
            
            word_count = len(normalized.split())
            
            # Single-word material queries: return multiple matches
            if word_count == 1:
                min_similarity = 0.25
                limit = 5
                logger.info("Single-word query detected → returning up to %d matches", limit)
                
                # Try exact first
                exact_result = MatchingService.perform_exact_match(description)
                if exact_result:
                    return [exact_result]  # Wrap in list for consistency
                
                # Return multiple fuzzy matches
                return MatchingService.perform_multiple_match(description, limit, min_similarity)
            
            # Multi-word queries: return single best match
            min_similarity_single = 0.6
            min_similarity_multiple = 0.4
            limit = 5

            # 1. Try exact
            result = MatchingService.perform_exact_match(description)

            # 2. Try fuzzy
            if not result:
                result = MatchingService.perform_fuzzy_match(description, min_similarity_single)

            # 3. Try multiple matches
            if not result:
                result = MatchingService.perform_multiple_match(description, limit, min_similarity_multiple)
            return result
        except Exception as e:
            logger.error("Error in perform_best_match: %s", str(e), exc_info=True)
            return None


    @staticmethod
    def search_candidates(term: str, limit: int = 10):
        logger.debug("search_candidates called term=%s limit=%d", term, limit)
        repo = DbAhsRepository()
        search_callable = getattr(repo, "search", None)

        if callable(search_callable):
            rows = search_callable(term, limit=limit)
        else:
            logger.warning("DbAhsRepository.search missing; falling back to by_name_candidates")
            cleaned = (term or "").strip()
            if not cleaned:
                return []
            rows = repo.by_name_candidates(cleaned)[:limit]

        return [
            {
                "source": "ahs",
                "id": row.id,
                "code": row.code,
                "name": row.name,
            }
            for row in rows
        ]