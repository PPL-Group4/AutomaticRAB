from __future__ import annotations
from dataclasses import dataclass
from typing import List, Protocol, Optional, Set, Tuple
from functools import lru_cache
from rapidfuzz import fuzz
import logging
import re

from automatic_job_matching.utils.text_normalizer import normalize_text
from automatic_job_matching.utils.unit_normalizer import (
    normalize_unit,
    infer_unit_from_description,
    units_are_compatible,
)
from automatic_job_matching.service.scoring import ConfidenceScorer, FuzzyConfidenceScorer
from automatic_job_matching.config.action_synonyms import (
    get_synonyms,
    has_synonyms,
    get_compound_materials,
    is_compound_material,
)
from automatic_job_matching.service.word_embeddings import SynonymExpander

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

@lru_cache(maxsize=5000)
def _norm_name(s: str) -> str:
    return normalize_text(s or "")


def _filter_by_unit(candidates: List[AhsRow], user_unit: Optional[str]) -> List[AhsRow]:
    """Filter candidates by unit compatibility.

    Priority:
    1. If user provides a unit, it has highest priority.
    2. If candidate’s inferred unit conflicts with the user’s unit → reject.
    3. If user’s unit is empty, fall back to inferred filtering.
    """
    if not user_unit:
        return candidates  # No unit provided, skip filtering entirely

    normalized_user = normalize_unit(user_unit)
    if not normalized_user:
        logger.debug("User unit '%s' could not be normalized - skipping unit filter", user_unit)
        return candidates

    filtered = []
    for candidate in candidates:
        inferred = infer_unit_from_description(candidate.name)

        # === user unit has higher priority ===
        # If inferred unit is missing, accept (we trust user)
        if not inferred:
            filtered.append(candidate)
            continue

        # If inferred unit conflicts, skip
        if not units_are_compatible(inferred, normalized_user):
            logger.debug(
                "Unit mismatch: candidate=%r inferred=%s user=%s (filtered out)",
                candidate.code,
                inferred,
                normalized_user,
            )
            continue

        # Otherwise, keep it
        filtered.append(candidate)
        logger.debug(
            "Unit match: candidate=%r inferred=%s user=%s",
            candidate.code,
            inferred,
            normalized_user,
        )

    logger.info(
        "Filtered by unit (user=%s): %d/%d candidates remain",
        normalized_user,
        len(filtered),
        len(candidates),
    )
    return filtered


class WordWeightConfig:
    """Dynamic word weight configuration based on AHSP construction database patterns."""

    HIGH_WEIGHT = 3.0
    NORMAL_WEIGHT = 1.0
    LOW_WEIGHT = 0.3
    ULTRA_LOW_WEIGHT = 0.15

    ACTION_PATTERNS = [
        r'^pe[mr]',
        r'^pen[yg]?',
        r'^di',
        r'an$',
        r'kan$',
        r'^(pasang|bongkar|ganti|bangun|renovasi|perbaik|buat|install)',
        r'^(galian|urugan|pemadatan|pembuangan|pengangkutan)',
        r'^(pengukuran|pengecatan|pelituran|pemolesan|finishing)',
        r'^(plester|acian|grouting|curing|ereksi|fabrikasi)',
    ]

    MATERIAL_PATTERNS = [
        r'^(beton|besi|baja|kayu|bambu|pasir|kerikil|semen|cat|pipa|kabel)',
        r'^(genteng|aspal|keramik|granit|marmer|kaca|aluminium|tembaga)',
        r'^(pvc|upvc|hdpe|grc|gypsum|fiber|plywood|triplek|multiplek)',
        r'(beton|besi|baja|kayu|bambu|pasir|kerikil|semen|cat|pipa|kabel)$',
    ]

    GENERIC_WORDS = {
        'untuk', 'dengan', 'pada', 'dari', 'dan', 'atau', 'di', 'ke', 'yang',
        'adalah', 'oleh', 'sebagai', 'dalam', 'akan', 'telah', 'sudah', 'belum',
        'per', 'setiap', 'tiap', 'semua', 'seluruh', 'beberapa', 'banyak',
        'sedikit', 'lebih', 'kurang', 'sama', 'lain', 'baru', 'lama',
    }

    @staticmethod
    def _is_action_word(word: str) -> bool:
        return any(re.search(pattern, word) for pattern in WordWeightConfig.ACTION_PATTERNS)

    @staticmethod
    def _is_technical_word(word: str) -> bool:
        if any(re.search(pattern, word) for pattern in WordWeightConfig.MATERIAL_PATTERNS):
            return True
        if len(word) >= 6 and word not in WordWeightConfig.GENERIC_WORDS:
            return True
        return False

    @staticmethod
    def get_word_weight(word: str) -> float:
        if word in WordWeightConfig.GENERIC_WORDS:
            return WordWeightConfig.ULTRA_LOW_WEIGHT
        if WordWeightConfig._is_technical_word(word):
            return WordWeightConfig.HIGH_WEIGHT
        if WordWeightConfig._is_action_word(word):
            return WordWeightConfig.NORMAL_WEIGHT
        if len(word) <= 2:
            return WordWeightConfig.LOW_WEIGHT
        return WordWeightConfig.NORMAL_WEIGHT


class SimilarityCalculator:
    def __init__(self, word_weight_config: WordWeightConfig):
        self.word_weight_config = word_weight_config

    def calculate_sequence_similarity(self, query: str, candidate: str) -> float:
        """Calculate sequence similarity using rapidfuzz."""
        return fuzz.ratio(query, candidate) / 100.0

    def calculate_partial_similarity(self, query: str, candidate: str) -> float:
        """Calculate partial similarity with word importance weighting."""
        query_words = query.split()
        candidate_words = candidate.split()

        if not query_words:
            return 0.0

        matched_weight, total_weight, _ = self._evaluate_word_matches(
            query_words,
            candidate_words,
            capture_breakdown=False,
        )

        if total_weight == 0:
            return 0.0

        return matched_weight / total_weight

    def explain_similarity(self, query: str, candidate: str) -> dict:
        """Return detailed similarity metrics for debugging or UI insights."""
        query_words = query.split()
        candidate_words = candidate.split()

        if not query_words:
            return {
                "sequence_score": 0.0,
                "partial_score": 0.0,
                "matched_weight": 0.0,
                "total_weight": 0.0,
                "word_breakdown": [],
            }

        matched_weight, total_weight, breakdown = self._evaluate_word_matches(
            query_words,
            candidate_words,
            capture_breakdown=True,
        )

        sequence_score = self.calculate_sequence_similarity(query, candidate)
        partial_score = (matched_weight / total_weight) if total_weight else 0.0

        return {
            "sequence_score": sequence_score,
            "partial_score": partial_score,
            "matched_weight": matched_weight,
            "total_weight": total_weight,
            "word_breakdown": breakdown,
        }

    def _evaluate_word_matches(
        self,
        query_words: List[str],
        candidate_words: List[str],
        capture_breakdown: bool,
    ) -> Tuple[float, float, List[dict]]:
        matched_weight = 0.0
        total_weight = 0.0
        breakdown: List[dict] = []

        for query_word in query_words:
            word_weight = self.word_weight_config.get_word_weight(query_word)
            total_weight += word_weight

            best_match, best_word, match_type = self._find_best_match(
                query_word,
                candidate_words,
            )

            matched_weight += word_weight * best_match

            if capture_breakdown:
                breakdown.append(self._build_breakdown_entry(
                    query_word,
                    best_word,
                    match_type,
                    best_match,
                    word_weight,
                ))

        return matched_weight, total_weight, breakdown

    def _find_best_match(
        self,
        query_word: str,
        candidate_words: List[str],
    ) -> Tuple[float, Optional[str], str]:
        best_match = 0.0
        best_word: Optional[str] = None
        match_type = "none"

        for candidate_word in candidate_words:
            if query_word == candidate_word:
                return 1.0, candidate_word, "exact"

            if self._is_substring_overlap(query_word, candidate_word):
                ratio = self._calculate_overlap_ratio(query_word, candidate_word)
                if ratio > best_match:
                    best_match = ratio
                    best_word = candidate_word
                    match_type = "substring"

        return best_match, best_word, match_type

    @staticmethod
    def _is_substring_overlap(query_word: str, candidate_word: str) -> bool:
        return query_word in candidate_word or candidate_word in query_word

    @staticmethod
    def _calculate_overlap_ratio(query_word: str, candidate_word: str) -> float:
        max_length = max(len(query_word), len(candidate_word))
        if max_length == 0:
            return 0.0
        overlap = min(len(query_word), len(candidate_word))
        return overlap / max_length

    def _build_breakdown_entry(
        self,
        query_word: str,
        best_word: Optional[str],
        match_type: str,
        best_match: float,
        word_weight: float,
    ) -> dict:
        sequence_ratio = (
            fuzz.ratio(query_word, best_word) / 100.0
            if best_word
            else 0.0
        )
        return {
            "query_word": query_word,
            "matched_word": best_word,
            "match_type": match_type if best_match > 0 else "none",
            "score": round(best_match, 3),
            "weight": round(word_weight, 3),
            "weighted_score": round(word_weight * best_match, 3),
            "sequence_ratio": round(sequence_ratio, 3),
        }

class CandidateProvider:
    def __init__(self, repository: AhsRepository, synonym_expander: SynonymExpander = None):
        self._repository = repository
        self._synonym_expander = synonym_expander
        self._compound_materials = get_compound_materials()

    def get_candidates_by_head_token(self, normalized_input: str, unit: Optional[str] = None) -> List[AhsRow]:
        """Get candidates and filter by unit if provided."""
        logger.debug("CandidateProvider: input=%s, unit=%s", normalized_input, unit)

        # Get candidates using existing logic
        candidates = self._get_candidates_internal(normalized_input)

        # Apply unit filter
        if unit:
            candidates = _filter_by_unit(candidates, unit)

        return candidates

    def _get_candidates_internal(self, normalized_input: str) -> List[AhsRow]:
        """Internal method to get candidates without unit filtering."""
        if not normalized_input:
            return self._repository.get_all_ahs()

        words = normalized_input.split()
        head = words[0]

        material_words = [w for w in words if WordWeightConfig._is_technical_word(w)]
        action_words = [w for w in words if WordWeightConfig._is_action_word(w)]
        significant_words = [
            w for w in words
            if w not in WordWeightConfig.GENERIC_WORDS
            and len(w) >= 4
        ]

        detected_compounds = self._detect_compound_materials_in_input(normalized_input)

        # Try single-word material query
        single_word_result = self._try_single_word_material_query(
            words, material_words, detected_compounds
        )
        if single_word_result is not None:
            return single_word_result

        # Try multi-word query
        multi_word_result = self._try_multi_word_query(
            significant_words, material_words, action_words, detected_compounds
        )
        if multi_word_result is not None:
            return multi_word_result

        # Try material filter mode
        material_filter_result = self._try_material_filter_mode(material_words)
        if material_filter_result is not None:
            return material_filter_result

        # Fallback to head token + synonym expansion
        return self._get_candidates_with_synonym_expansion(head)

    def _try_single_word_material_query(
        self,
        words: List[str],
        material_words: List[str],
        detected_compounds: dict
    ) -> Optional[List[AhsRow]]:
        """Handle single-word material queries."""
        if len(words) == 1:
            word = words[0]
            if WordWeightConfig._is_technical_word(word) or is_compound_material(word):
                logger.info("Single-word material query detected: '%s'", word)
                all_candidates = self._repository.get_all_ahs()

                filtered = self._filter_candidates_any_material([word], all_candidates, detected_compounds)
                if filtered:
                    logger.info("Single material query returned %d candidates", len(filtered))
                    return filtered
        return None

    def _try_multi_word_query(
        self,
        significant_words: List[str],
        material_words: List[str],
        action_words: List[str],
        detected_compounds: dict
    ) -> Optional[List[AhsRow]]:
        """Try multi-word query matching with optimized candidate pool."""
        if len(significant_words) >= 2:
            logger.info("Multi-word query with %d significant words", len(significant_words))

            # Optimize: Try head token first to get smaller candidate pool
            head_candidates = self._repository.by_name_candidates(significant_words[0])

            if head_candidates and len(head_candidates) < 1000:
                # Use smaller pool if available
                candidates = self._filter_candidates_all_words(
                    significant_words, material_words, action_words, head_candidates, detected_compounds
                )
                if candidates:
                    logger.info("Multi-word query (head token) returned %d candidates", len(candidates))
                    return candidates

            # Fall back to all candidates if head token yields nothing or too many
            all_candidates = self._repository.get_all_ahs()
            candidates = self._filter_candidates_all_words(
                significant_words, material_words, action_words, all_candidates, detected_compounds
            )

            if candidates:
                logger.info("Multi-word query returned %d candidates", len(candidates))
                return candidates

            fallback = self._try_multi_word_fallback(
                significant_words, material_words, all_candidates, detected_compounds
            )
            if fallback:
                return fallback

        return None

    def _filter_candidates_all_words(
        self,
        significant_words: List[str],
        material_words: List[str],
        action_words: List[str],
        candidates: List[AhsRow],
        detected_compounds: dict
    ) -> List[AhsRow]:
        """Filter candidates that match all significant words."""
        filtered = []

        for candidate in candidates:
            candidate_name = _norm_name(candidate.name)
            matched_count = self._count_matched_words(
                significant_words, material_words, action_words,
                candidate_name, detected_compounds
            )

            if matched_count >= len(significant_words):
                filtered.append(candidate)

        return filtered

    def _count_matched_words(
        self,
        significant_words: List[str],
        material_words: List[str],
        action_words: List[str],
        candidate_name: str,
        detected_compounds: dict
    ) -> int:
        """Count how many significant words are matched in candidate."""
        matched = 0
        for word in significant_words:
            if self._check_word_match(word, material_words, action_words, candidate_name, detected_compounds):
                matched += 1
        return matched

    def _check_word_match(
        self,
        word: str,
        material_words: List[str],
        action_words: List[str],
        candidate_name: str,
        detected_compounds: dict
    ) -> bool:
        """Check if a word matches in candidate name."""
        if word in candidate_name:
            return True
        if self._check_synonym_match(word, candidate_name):
            return True
        if self._check_fuzzy_match(word, candidate_name):
            return True
        if self._check_compound_material_match(word, candidate_name, detected_compounds):
            return True
        return False

    def _check_synonym_match(self, word: str, candidate_name: str) -> bool:
        """Check if word or its synonyms appear in candidate."""
        if not has_synonyms(word):
            return False

        synonyms = get_synonyms(word)
        match = next((syn for syn in synonyms if syn in candidate_name), None)
        if match:
            logger.debug("Synonym match: '%s' -> '%s'", word, match)
        return bool(match)

    def _check_fuzzy_match(self, word: str, candidate_name: str) -> bool:
        """Check fuzzy match for longer words with early termination."""
        if len(word) < 6:
            return False

        # Quick rejection: get first character for prefix check
        word_first_char = word[0]

        for candidate_word in candidate_name.split():
            if len(candidate_word) < 6:
                continue

            # Early termination: skip if first character doesn't match
            if candidate_word[0] != word_first_char:
                continue

            ratio = fuzz.ratio(word, candidate_word) / 100.0
            if ratio >= 0.8:
                logger.debug("Fuzzy match: '%s' ≈ '%s' (%.2f)", word, candidate_word, ratio)
                return True
        return False

    def _check_compound_material_match(
        self,
        word: str,
        candidate_name: str,
        detected_compounds: dict
    ) -> bool:
        """Check if word is part of a compound material."""
        if word in detected_compounds:
            compound = detected_compounds[word]
            if self._candidate_contains_compound(candidate_name, compound):
                logger.debug("Compound material match: '%s' in compound '%s'", word, compound)
                return True
        return False

    def _try_multi_word_fallback(
        self,
        significant_words: List[str],
        material_words: List[str],
        candidates: List[AhsRow],
        detected_compounds: dict
    ) -> Optional[List[AhsRow]]:
        """Fallback to material-only filter for multi-word queries."""
        if material_words:
            logger.info("Multi-word fallback: filtering by materials only")
            filtered = self._filter_candidates_any_material(
                material_words, candidates, detected_compounds
            )
            if filtered:
                logger.info("Multi-word fallback returned %d candidates", len(filtered))
                return filtered
        return None

    def _filter_candidates_any_material(
        self,
        material_words: List[str],
        candidates: List[AhsRow],
        detected_compounds: dict
    ) -> List[AhsRow]:
        """Filter candidates matching any material word."""
        filtered = []
        for candidate in candidates:
            candidate_name = _norm_name(candidate.name)
            if self._candidate_matches_any_material(
                candidate_name, material_words, detected_compounds
            ):
                filtered.append(candidate)
        return filtered

    def _candidate_matches_any_material(
        self,
        candidate_name: str,
        material_words: List[str],
        detected_compounds: dict
    ) -> bool:
        """Check if candidate matches any material word."""
        for material in material_words:
            if material in candidate_name:
                return True

            if material in detected_compounds:
                compound = detected_compounds[material]
                if self._candidate_contains_compound(candidate_name, compound):
                    return True

            if has_synonyms(material):
                synonyms = get_synonyms(material)
                for syn in synonyms:
                    if syn in candidate_name:
                        return True

        return False

    def _try_material_filter_mode(self, material_words: List[str]) -> Optional[List[AhsRow]]:
        """Try material-only filter mode."""
        if not material_words:
            return None

        logger.info("Material filter mode: filtering by %d materials", len(material_words))
        all_candidates = self._repository.get_all_ahs()
        detected_compounds = {mat: mat for mat in material_words if is_compound_material(mat)}

        filtered = self._filter_candidates_any_material(
            material_words, all_candidates, detected_compounds
        )

        if filtered:
            logger.info("Material filter returned %d candidates", len(filtered))
            return filtered

        return None

    def _get_candidates_with_synonym_expansion(self, head_token: str) -> List[AhsRow]:
        """Get candidates using head token and synonyms."""
        logger.debug("Getting candidates for head_token: %s", head_token)

        candidates = self._repository.by_name_candidates(head_token)

        tokens_to_search = self._get_synonyms_to_search(head_token)

        for token in tokens_to_search:
            if token != head_token:
                additional = self._repository.by_name_candidates(token)
                candidates.extend(additional)

        candidates = self._deduplicate_candidates(candidates)

        logger.info("Total candidates after synonym expansion: %d", len(candidates))
        return candidates

    def _get_synonyms_to_search(self, head_token: str) -> Set[str]:
        """Get set of tokens including synonyms to search."""
        tokens_to_search = {head_token}

        if has_synonyms(head_token):
            synonyms = get_synonyms(head_token)
            tokens_to_search.update(synonyms)
            logger.debug("Found %d synonyms for '%s'", len(synonyms), head_token)

        if self._synonym_expander:
            try:
                embedding_synonyms = self._synonym_expander.get_synonyms(head_token, top_k=3)
                if embedding_synonyms:
                    tokens_to_search.update(embedding_synonyms)
                    logger.debug("Added %d embedding-based synonyms", len(embedding_synonyms))
            except Exception as e:
                logger.debug("Embedding synonym expansion failed: %s", e)

        return tokens_to_search

    def _deduplicate_candidates(self, candidates: List[AhsRow]) -> List[AhsRow]:
        """Remove duplicate candidates based on code."""
        seen = set()
        deduplicated = []
        for candidate in candidates:
            if candidate.code not in seen:
                seen.add(candidate.code)
                deduplicated.append(candidate)
        return deduplicated

    def _detect_compound_materials_in_input(self, normalized_input: str) -> dict:
        """Detect compound materials in input and map components to full compound."""
        detected = {}
        for compound in self._compound_materials:
            if compound in normalized_input:
                components = compound.split()
                for component in components:
                    if len(component) >= 3:
                        detected[component] = compound
                logger.debug("Detected compound material: '%s'", compound)
        return detected

    def _candidate_contains_compound(self, candidate_name: str, compound: str) -> bool:
        """Check if candidate contains all parts of compound material."""
        compound_parts = compound.split()
        return all(part in candidate_name for part in compound_parts)


class MatchingProcessor:
    def __init__(self, similarity_calculator: SimilarityCalculator, candidate_provider: CandidateProvider, min_similarity: float = 0.6):
        self._similarity_calculator = similarity_calculator
        self._candidate_provider = candidate_provider
        self._min_similarity = max(0.0, min(1.0, min_similarity))

    def find_best_match(self, query: str, unit: Optional[str] = None) -> Optional[dict]:
        """Find best match with strict unit filtering."""
        logger.debug("Finding best fuzzy match for query=%s unit=%s", query, unit)
        normalized_query = _norm_name(query)
        if not normalized_query:
            return None

        candidates = self._candidate_provider.get_candidates_by_head_token(normalized_query, unit)
        if not candidates:
            logger.info("No candidates after unit filtering for query=%r unit=%r", query, unit)
            return None

        best_match = None
        best_score = 0.0

        for candidate in candidates:
            candidate_name = _norm_name(candidate.name)
            if not candidate_name:
                continue

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
                    "matched_on": "name"
                }

        if best_match:
            logger.info("Best fuzzy match score=%.4f (unit=%s)", best_score, unit)
        return best_match

    def find_multiple_matches(self, query: str, limit: int = 5, unit: Optional[str] = None) -> List[dict]:
        """Find multiple matches with strict unit filtering."""
        logger.debug("Finding up to %d fuzzy matches for query=%s unit=%s", limit, query, unit)
        if limit <= 0:
            return []

        normalized_query = _norm_name(query)
        if not normalized_query:
            return []

        candidates = self._candidate_provider.get_candidates_by_head_token(normalized_query, unit)
        if not candidates:
            logger.info("No candidates after unit filtering for query=%r unit=%r", query, unit)
            return []

        matches = []

        for candidate in candidates:
            candidate_name = _norm_name(candidate.name)
            if not candidate_name:
                continue

            seq_score = self._similarity_calculator.calculate_sequence_similarity(normalized_query, candidate_name)
            partial_score = self._similarity_calculator.calculate_partial_similarity(normalized_query, candidate_name)
            similarity_score = max(seq_score, partial_score)

            if similarity_score >= self._min_similarity:
                match_dict = {
                    "source": "ahs",
                    "id": candidate.id,
                    "code": candidate.code,
                    "name": candidate.name,
                    "matched_on": "name",
                    "_internal_score": similarity_score
                }
                matches.append((similarity_score, match_dict))

        matches.sort(key=lambda x: x[0], reverse=True)
        logger.info("Multiple fuzzy matches found=%d (unit=%s)", len(matches), unit)
        return [match[1] for match in matches[:limit]]

    def find_matches_with_explanations(self, query: str, limit: int = 5, unit: Optional[str] = None) -> List[dict]:
        """Find matches along with similarity breakdown for each candidate."""
        logger.debug("Finding matches with explanations (limit=%d) query=%s unit=%s", limit, query, unit)

        normalized_query = _norm_name(query)
        if limit <= 0 or not normalized_query:
            return []

        candidates = self._candidate_provider.get_candidates_by_head_token(normalized_query, unit)
        if not candidates:
            logger.info("No candidates after unit filtering for query=%r unit=%r", query, unit)
            return []

        matches = []

        for candidate in candidates:
            candidate_name = _norm_name(candidate.name)
            if not candidate_name:
                continue

            explanation = self._similarity_calculator.explain_similarity(normalized_query, candidate_name)
            similarity_score = max(explanation["sequence_score"], explanation["partial_score"])

            if similarity_score >= self._min_similarity:
                matches.append((
                    similarity_score,
                    {
                        "source": "ahs",
                        "id": candidate.id,
                        "code": candidate.code,
                        "name": candidate.name,
                        "matched_on": "name",
                        "similarity": round(similarity_score, 4),
                        "scores": {
                            "sequence": round(explanation["sequence_score"], 4),
                            "partial": round(explanation["partial_score"], 4),
                        },
                        "weights": {
                            "matched": round(explanation["matched_weight"], 4),
                            "total": round(explanation["total_weight"], 4),
                        },
                        "explanation": list(explanation["word_breakdown"]),
                    },
                ))

        matches.sort(key=lambda x: x[0], reverse=True)
        logger.info("Matches with explanations found=%d (unit=%s)", len(matches), unit)
        return [match[1] for match in matches[:limit]]


class FuzzyMatcher:
    def __init__(self, repo: AhsRepository, min_similarity: float = 0.6, scorer: ConfidenceScorer | None = None, synonym_expander: SynonymExpander = None):
        self.repo = repo
        self.min_similarity = max(0.0, min(1.0, min_similarity))
        self.scorer: ConfidenceScorer = scorer or FuzzyConfidenceScorer()
        self._similarity_calculator = SimilarityCalculator(WordWeightConfig())
        self._candidate_provider = CandidateProvider(repo, synonym_expander)
        self._matching_processor = MatchingProcessor(self._similarity_calculator, self._candidate_provider, min_similarity)

    def match(self, description: str, unit: Optional[str] = None) -> Optional[dict]:
        """Match description with optional unit."""
        logger.debug("FuzzyMatcher.match called with description=%r unit=%r", description, unit)
        if not description:
            return None
        return self._matching_processor.find_best_match(description.strip(), unit=unit)

    def find_multiple_matches(self, description: str, limit: int = 5, unit: Optional[str] = None) -> List[dict]:
        """Find multiple matches with optional unit."""
        logger.debug("FuzzyMatcher.find_multiple_matches called with description=%r unit=%r", description, unit)
        if not description or limit <= 0:
            return []
        return self._matching_processor.find_multiple_matches(description.strip(), limit, unit=unit)

    def find_matches_with_explanations(self, description: str, limit: int = 5, unit: Optional[str] = None) -> List[dict]:
        """Find matches while exposing similarity breakdown details."""
        logger.debug(
            "FuzzyMatcher.find_matches_with_explanations called with description=%r unit=%r",
            description,
            unit,
        )
        if not description or limit <= 0:
            return []
        return self._matching_processor.find_matches_with_explanations(description.strip(), limit, unit=unit)

    def match_with_confidence(self, description: str, unit: Optional[str] = None) -> Optional[dict]:
        """Match with confidence scoring and optional unit."""
        logger.debug("FuzzyMatcher.match_with_confidence called with description=%r unit=%r", description, unit)
        if not description:
            return None

        normalized_query = _norm_name(description.strip())
        if not normalized_query:
            return None

        expanded_query = self._expand_query_for_scoring(normalized_query)
        logger.info("Query for scoring: '%s' → '%s'", normalized_query, expanded_query)

        candidates = self._candidate_provider.get_candidates_by_head_token(normalized_query, unit)
        if not candidates:
            logger.info("No candidates after unit filtering for query=%r unit=%r", description, unit)
            return None

        best = None
        best_conf = 0.0

        for cand in candidates:
            norm_cand = _norm_name(cand.name)
            if not norm_cand:
                continue

            conf_original = self.scorer.score(normalized_query, norm_cand)
            conf_expanded = self.scorer.score(expanded_query, norm_cand) if expanded_query != normalized_query else 0.0
            conf = max(conf_original, conf_expanded)

            if conf >= self.min_similarity and conf > best_conf:
                best_conf = conf
                best = cand

        if best:
            logger.info("Best confidence match id=%s score=%.4f (unit=%s)", best.id, best_conf, unit)
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

    def find_multiple_matches_with_confidence(self, description: str, limit: int = 5, unit: Optional[str] = None) -> List[dict]:
        """Find multiple matches with confidence and optional unit."""
        logger.debug("FuzzyMatcher.find_multiple_matches_with_confidence called (limit=%d) desc=%r unit=%r", limit, description, unit)
        if not description or limit <= 0:
            return []

        normalized_query = _norm_name(description.strip())
        if not normalized_query:
            return []

        expanded_query = self._expand_query_for_scoring(normalized_query)
        logger.info("Query for scoring: '%s' → '%s'", normalized_query, expanded_query)

        candidates = self._candidate_provider.get_candidates_by_head_token(normalized_query, unit)
        if not candidates:
            logger.info("No candidates after unit filtering for query=%r unit=%r", description, unit)
            return []

        results = []

        for cand in candidates:
            norm_cand = _norm_name(cand.name)
            if not norm_cand:
                continue

            conf_original = self.scorer.score(normalized_query, norm_cand)
            conf_expanded = self.scorer.score(expanded_query, norm_cand) if expanded_query != normalized_query else 0.0
            conf = max(conf_original, conf_expanded)

            if conf >= self.min_similarity:
                result_dict = {
                    "source": "ahs",
                    "id": cand.id,
                    "code": cand.code,
                    "name": cand.name,
                    "matched_on": "name",
                    "confidence": round(conf, 4)
                }
                results.append((conf, result_dict))

        results.sort(key=lambda x: x[0], reverse=True)
        logger.info("Found %d matches with confidence >= %.2f (unit=%s)", len(results), self.min_similarity, unit)
        return [result[1] for result in results[:limit]]

    def _expand_query_for_scoring(self, normalized_query: str) -> str:
        """Expand query with synonyms for scoring."""
        words = normalized_query.split()
        expanded_words = []

        for word in words:
            expanded_words.append(word)
            if has_synonyms(word):
                synonyms = get_synonyms(word)
                expanded_words.extend(synonyms[:2])

        return " ".join(expanded_words)

    # Legacy methods for backward compatibility
    def match_by_name(self, name: str) -> Optional[dict]:
        """Legacy method: match by name."""
        logger.debug("FuzzyMatcher.match_by_name (legacy) called with name=%r", name)
        return self.match(name)

    def search(self, query: str, limit: int = 5) -> List[dict]:
        """Legacy method: search."""
        logger.debug("FuzzyMatcher.search (legacy) called with query=%r limit=%d", query, limit)
        return self.find_multiple_matches(query, limit)
