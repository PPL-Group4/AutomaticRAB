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
    def determine_status(result):
        if isinstance(result, dict) and result:
            if "alternatives" in result:
                return "unit mismatch"

            status = result.get("status")
            if status == "unit_mismatch":
                return "unit mismatch"
            if status in {"found", "similar"}:
                return status

            confidence = result.get("confidence", 1.0)
            return "found" if confidence == 1.0 else "similar"

        if isinstance(result, list):
            if not result:
                return "not found"
            if len(result) == 1:
                return "similar"
            return f"found {len(result)} similar"

        if result:
            return "found"

        return "not found"

    @staticmethod
    def _extract_bulk_fields(item):
        if not isinstance(item, dict):
            return None, None

        return item.get("description"), item.get("unit")

    @staticmethod
    def _build_bulk_response(description, unit, status, match, error=None):
        response = {
            "description": description,
            "unit": unit,
            "status": status,
            "match": match,
        }

        if error is not None:
            response["error"] = error

        return response

    @staticmethod
    def perform_bulk_best_match(requests):
        items = list(requests or [])
        logger.info("perform_bulk_best_match called with %d items", len(items))

        if not items:
            return []

        responses = []

        for idx, item in enumerate(items):
            description, unit = MatchingService._extract_bulk_fields(item)

            try:
                match = MatchingService.perform_best_match(description, unit=unit) if description else None
                status = MatchingService.determine_status(match)
                responses.append(
                    MatchingService._build_bulk_response(description, unit, status, match)
                )
            except Exception as exc:
                logger.error("Error in perform_bulk_best_match (index=%d): %s", idx, exc, exc_info=True)
                responses.append(
                    MatchingService._build_bulk_response(
                        description,
                        unit,
                        "error",
                        None,
                        error=str(exc),
                    )
                )

        return responses

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

            # === Single-word material queries ===
            if word_count == 1:
                min_similarity = 0.25
                limit = 5
                logger.info("Single-word query detected → returning up to %d matches", limit)

                # Try exact first
                exact_result = MatchingService.perform_exact_match(description)
                if exact_result:
                    return [exact_result]

                # Try fuzzy/multiple with unit
                primary = MatchingService.perform_multiple_match(description, limit, min_similarity, unit=unit)
                if primary:
                    return primary

                # Fallback: try again ignoring unit
                alt_matches = MatchingService.perform_multiple_match(description, limit, min_similarity, unit=None)
                if alt_matches:
                    for m in alt_matches:
                        m["unit_mismatch"] = True
                    return {
                        "message": "No matches with the same unit found. Showing similar options with different units.",
                        "alternatives": alt_matches,
                    }

                return None

            # === Multi-word queries ===
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

            # === Fallback: no matches at all, try ignoring unit ===
            if not result:
                alt_matches = MatchingService.perform_multiple_match(description, limit, min_similarity_multiple, unit=None)
                if alt_matches:
                    for m in alt_matches:
                        m["unit_mismatch"] = True
                    return {
                        "message": "No matches with the same unit found. Showing similar options with different units.",
                        "alternatives": alt_matches,
                    }
                
            if isinstance(result, dict):
                result_unit = result.get("unit")
                if unit and result_unit and result_unit != unit:
                    result["unit_mismatch"] = True
                else:
                    result["unit_mismatch"] = False

                if result.get("unit_mismatch"):
                    result["status"] = "unit_mismatch"
                elif result.get("confidence", 1.0) == 1.0:
                    result["status"] = "found"
                else:
                    result["status"] = "similar"

            return result

        except Exception as e:
            logger.error("Error in perform_best_match: %s", str(e), exc_info=True)
            return None
