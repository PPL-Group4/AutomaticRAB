import logging

from automatic_job_matching.repository.combined_ahs_repo import CombinedAhsRepository
from automatic_job_matching.service.exact_matcher import ExactMatcher
from automatic_job_matching.service.fuzzy_matcher import FuzzyMatcher
from automatic_job_matching.service.scoring import FuzzyConfidenceScorer
from automatic_job_matching.utils.text_normalizer import normalize_text
from automatic_job_matching.service.translation_service import TranslationService
from automatic_job_matching.service.abbreviation_service import AbbreviationService


logger = logging.getLogger(__name__)

class MatchingService:
    translator = TranslationService()
    _shared_repo = CombinedAhsRepository()
    
    @staticmethod
    def perform_exact_match(description):
        logger.info("perform_exact_match called (len=%d)", len(description))

        try:
            matcher = ExactMatcher(MatchingService._shared_repo)
            result = matcher.match(description)
            logger.debug("Exact match result: %s", result)
            return result
        except Exception as e:
            logger.error("Error in perform_exact_match: %s", str(e), exc_info=True)
            return None

    @staticmethod
    def perform_fuzzy_match(description, min_similarity=0.6, unit=None):
        logger.info("perform_fuzzy_match called (len=%d, min_similarity=%.2f, unit=%s)",
                    len(description), min_similarity, unit)

        try:
            matcher = FuzzyMatcher(MatchingService._shared_repo, min_similarity, scorer=FuzzyConfidenceScorer())
            confidence_result = getattr(matcher, 'match_with_confidence', None)
            if callable(confidence_result):
                result = confidence_result(description, unit=unit)
            else:
                result = matcher.match(description, unit=unit)

            logger.debug("Fuzzy match result: %s", result)
            return result
        except Exception as e:
            logger.error("Error in perform_fuzzy_match: %s", str(e), exc_info=True)
            return None

    @staticmethod
    def perform_multiple_match(description, limit=5, min_similarity=0.6, unit=None):
        logger.info("perform_multiple_match called (len=%d, limit=%d, min_similarity=%.2f, unit=%s)",
                    len(description), limit, min_similarity, unit)

        try:
            matcher = FuzzyMatcher(MatchingService._shared_repo, min_similarity, scorer=FuzzyConfidenceScorer())
            confidence_multi = getattr(matcher, 'find_multiple_matches_with_confidence', None)

            if callable(confidence_multi):
                results = confidence_multi(description, limit, unit=unit)
            else:
                results = matcher.find_multiple_matches(description, limit, unit=unit)

            logger.debug("Multiple fuzzy match results count=%d", len(results))
            return results
        except Exception as e:
            logger.error("Error in perform_multiple_match: %s", str(e), exc_info=True)
            return []

    @staticmethod
    def perform_best_match(description: str, unit: str = None):
        logger.info("perform_best_match called (len=%d, unit=%s)", len(description), unit)

        translated_text = MatchingService.translator.translate_to_indonesian(description)
        description = translated_text or description
        description = AbbreviationService.expand(description)

        try:
            normalized = normalize_text(description)

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
                    return [exact_result]

                # Return multiple fuzzy matches with unit
                return MatchingService.perform_multiple_match(description, limit, min_similarity, unit=unit)

            # Multi-word queries: return single best match
            min_similarity_single = 0.9
            min_similarity_multiple = 0.6
            limit = 10

            # 1. Try exact
            result = MatchingService.perform_exact_match(description)

            # 2. Try fuzzy with unit
            if not result:
                result = MatchingService.perform_fuzzy_match(description, min_similarity_single, unit=unit)

            # 3. Try multiple matches with unit
            if not result:
                result = MatchingService.perform_multiple_match(description, limit, min_similarity_multiple, unit=unit)

            return result
        except Exception as e:
            logger.error("Error in perform_best_match: %s", str(e), exc_info=True)
            return None
