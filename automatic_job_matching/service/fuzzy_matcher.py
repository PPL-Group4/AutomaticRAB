from __future__ import annotations
from dataclasses import dataclass
from typing import List, Protocol, Optional
import difflib
import logging
import re

from automatic_job_matching.utils.text_normalizer import normalize_text
from automatic_job_matching.service.scoring import ConfidenceScorer, FuzzyConfidenceScorer
from automatic_job_matching.config.action_synonyms import get_synonyms, has_synonyms, get_compound_materials, is_compound_material
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

def _norm_name(s: str) -> str:
    return normalize_text(s or "")

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
    
    GENERIC_WORDS = {
        'untuk', 'dan', 'atau', 'dengan', 'pada', 'di', 'ke', 'dari', 
        'yang', 'ini', 'itu', 'tersebut', 'sebagai', 'antara', 'oleh',
        'dalam', 'luar', 'atas', 'bawah', 'semua', 'beberapa',
        'cara', 'secara', 'tiap', 'per', 'setiap', 'hingga', 'sampai',
        'volume', 'ukuran', 'lebar', 'tinggi', 'item', 'jenis',
        'bagian',
    }
    
    TECHNICAL_INDICATORS = {
        'keramik', 'beton', 'semen', 'besi', 'baja', 'kayu', 'aluminium', 
        'pvc', 'gypsum', 'granit', 'marmer', 'kaca', 'aspal',
        'hollow', 'batako', 'hebel', 'conblock', 'roster', 'rooster',
        'triplek', 'multiplek', 'plywood', 'partikel', 'mdf',
        'tegel', 'teraso', 'homogeneous', 'porselen', 'teralux',
        'pipa', 'kabel', 'balok', 'kolom', 'sloof', 'pondasi', 'rangka',
        'dinding', 'lantai', 'atap', 'genteng', 'pintu', 'jendela',
        'tangga', 'railing', 'pagar', 'kanopi', 'plafon', 'ceiling',
        'bekisting', 'tulangan', 'wiremesh', 'angkur', 'baut',
        'logam', 'stainless', 'galvanis', 'tembaga', 'kuningan', 'seng',
        'fiber', 'fiberglass', 'composite', 'resin', 'epoxy',
        'listrik', 'plumbing', 'sanitasi', 'drainase', 'septic', 'ac',
        'lift', 'elevator', 'ventilasi', 'exhaust', 'hydrant', 'sprinkler',
        'cat', 'wallpaper', 'vinyl', 'karpet', 'parket', 'laminate',
        'nat', 'grout', 'menie', 'vernis', 'pelitur', 'plamir',
        'pasir', 'kerikil', 'sirtu', 'makadam', 'split', 'batu', 'cor',
        'wastafel', 'closet', 'kloset', 'urinoir', 'bathup', 'shower',
        'kran', 'floor', 'drain',
        'kusen', 'daun', 'engsel', 'kunci', 'handle', 'grendel',
        'jalusi', 'rolling', 'lipat',
        'meter', 'cm', 'mm', 'inch', 'm2', 'm3', 'kg', 'ton', 'liter',
        'diameter', 'tebal', 'panjang', 'dimensi', 'kapasitas',
        'pohon', 'palem', 'semak', 'rumput', 'tanaman', 'penutup',
        'polybag', 'pupuk', 'organik', 'anorganik',
        'mutu', 'kualitas', 'standar', 'spesifikasi', 'grade', 'class',
        'mpa', 'sni', 'iso', 'astm',
    }
    
    @classmethod
    def get_word_weight(cls, word: str) -> float:
        word_lower = word.lower()
        
        if word_lower in cls.GENERIC_WORDS:
            return cls.ULTRA_LOW_WEIGHT
        
        if cls._is_action_word(word_lower):
            return cls.LOW_WEIGHT
        
        if cls._is_technical_word(word_lower):
            return cls.HIGH_WEIGHT
        
        if re.search(r'\d', word_lower):
            return cls.HIGH_WEIGHT * 0.9
        
        if len(word_lower) <= 2:
            return cls.ULTRA_LOW_WEIGHT
        
        if len(word_lower) >= 10:
            return cls.NORMAL_WEIGHT * 1.3
        elif len(word_lower) >= 7:
            return cls.NORMAL_WEIGHT * 1.1
        elif len(word_lower) <= 3:
            return cls.NORMAL_WEIGHT * 0.8
        
        return cls.NORMAL_WEIGHT
    
    @classmethod
    def _is_action_word(cls, word: str) -> bool:
        for pattern in cls.ACTION_PATTERNS:
            if re.search(pattern, word):
                return True
        return False
    
    @classmethod
    def _is_technical_word(cls, word: str) -> bool:
        if word in cls.TECHNICAL_INDICATORS:
            return True
        
        for indicator in cls.TECHNICAL_INDICATORS:
            if len(indicator) >= 4 and indicator in word:
                return True
        
        return False

class SimilarityCalculator:
    def __init__(self, word_weight_config: WordWeightConfig = None):
        self._weight_config = word_weight_config or WordWeightConfig()
    
    @staticmethod
    def calculate_sequence_similarity(text1: str, text2: str) -> float:
        score = difflib.SequenceMatcher(None, text1, text2).ratio()
        logger.debug("Seq similarity between %r and %r = %.4f", text1, text2, score)
        return score
    
    def calculate_partial_similarity(self, text1: str, text2: str) -> float:
        if not text1 or not text2:
            return 0.0
            
        words1 = text1.split()
        words2 = text2.split()
        
        if not words1 or not words2:
            return 0.0
        
        weighted_jaccard = self._calculate_weighted_jaccard_similarity(words1, words2)
        weighted_partial = self._calculate_weighted_partial_score(words1, words2)
        
        score = max(weighted_jaccard, weighted_partial * 0.85)
        logger.debug("Weighted partial similarity between %r and %r = %.4f", text1, text2, score)
        return score
    
    def _calculate_weighted_jaccard_similarity(self, words1: List[str], words2: List[str]) -> float:
        set1 = set(words1)
        set2 = set(words2)
        
        intersection = set1.intersection(set2)
        union = set1.union(set2)
        
        if not union:
            return 0.0
        
        weighted_intersection = sum(
            self._weight_config.get_word_weight(word) for word in intersection
        )
        
        weighted_union = sum(
            self._weight_config.get_word_weight(word) for word in union
        )
        
        return weighted_intersection / weighted_union if weighted_union > 0 else 0.0
    
    def _calculate_weighted_partial_score(self, words1: List[str], words2: List[str]) -> float:
        weighted_words1 = [(w, self._weight_config.get_word_weight(w)) 
                           for w in words1 if len(w) >= 3]
        weighted_words2 = [(w, self._weight_config.get_word_weight(w)) 
                           for w in words2 if len(w) >= 3]
        
        if not weighted_words1 or not weighted_words2:
            return 0.0
        
        weighted_matches = 0.0
        total_weight = 0.0
        
        for w1, weight1 in weighted_words1:
            best_match_weight = 0.0
            for w2, weight2 in weighted_words2:
                if w1 in w2 or w2 in w1:
                    match_weight = max(weight1, weight2)
                    best_match_weight = max(best_match_weight, match_weight)
            
            if best_match_weight > 0:
                weighted_matches += best_match_weight
                total_weight += weight1
            else:
                total_weight += weight1
        
        return weighted_matches / total_weight if total_weight > 0 else 0.0
    
    @staticmethod
    def _calculate_jaccard_similarity(words1: set, words2: set) -> float:
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union) if union else 0.0
    
    @staticmethod
    def _calculate_partial_word_score(words1: set, words2: set) -> float:
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

class CandidateProvider:
    def __init__(self, repository: AhsRepository, synonym_expander: SynonymExpander = None):
        self._repository = repository
        self._synonym_expander = synonym_expander
        self._compound_materials = get_compound_materials()
    
    def get_candidates_by_head_token(self, normalized_input: str) -> List[AhsRow]:
        logger.debug("CandidateProvider: head_token search for input=%s", normalized_input)
        if not normalized_input:
            return self._repository.get_all_ahs()
        
        words = normalized_input.split()
        head = words[0]
        
        # Detect material and action words
        material_words = [w for w in words if WordWeightConfig._is_technical_word(w)]
        action_words = [w for w in words if WordWeightConfig._is_action_word(w)]
        significant_words = [
            w for w in words 
            if w not in WordWeightConfig.GENERIC_WORDS 
            and len(w) >= 4
        ]
        
        # DETECT COMPOUND MATERIALS IN INPUT
        detected_compounds = self._detect_compound_materials_in_input(normalized_input)
        logger.debug("Detected compound materials: %s", detected_compounds)
        
        # Single-word material query: strict material filtering
        if len(words) == 1 and material_words:
            material_word = material_words[0]
            logger.debug("Single material word '%s' → MATERIAL MODE", material_word)
            all_candidates = self._repository.get_all_ahs()
            
            # Check if it's a compound material
            if material_word in detected_compounds:
                compound_phrases = detected_compounds[material_word]
                filtered = [
                    c for c in all_candidates 
                    if self._candidate_contains_compound(c.name, material_word, compound_phrases)
                ]
            else:
                # Regular exact word matching
                filtered = [
                    c for c in all_candidates 
                    if material_word in _norm_name(c.name).split()
                ]
            
            if filtered:
                logger.info("Single-word material-mode: %d → %d candidates containing '%s'",
                           len(all_candidates), len(filtered), material_word)
                return filtered
        
        # Multi-word query with significant words: ALL-word matching with compound support
        elif len(significant_words) >= 2:
            logger.debug("Multi-word query: %s → ALL-WORD FILTER (compound-aware)", significant_words)
            all_candidates = self._repository.get_all_ahs()
            
            # Determine query type for better filtering strategy
            has_material = bool(material_words)
            has_action = bool(action_words)
            has_compound = bool(detected_compounds)
            
            logger.debug("Query analysis: material=%s, action=%s, compound=%s", has_material, has_action, has_compound)
            
            # Filter by ALL significant words (compound-aware matching)
            filtered = []
            for cand in all_candidates:
                norm_name = _norm_name(cand.name)
                name_words_set = set(norm_name.split())
                
                matched_count = 0
                
                for sig_word in significant_words:
                    # COMPOUND MATERIAL MATCHING (only for detected compounds)
                    if sig_word in detected_compounds:
                        compound_phrases = detected_compounds[sig_word]
                        if self._candidate_contains_compound(norm_name, sig_word, compound_phrases):
                            matched_count += 1
                            logger.debug("COMPOUND MATCH: '%s' found in '%s'", sig_word, cand.name)
                            continue
                    
                    # REGULAR WORD MATCHING (with synonyms)
                    word_matched = False
                    
                    # Check exact match
                    if sig_word in name_words_set:
                        word_matched = True
                        logger.debug("EXACT MATCH: '%s' found in '%s'", sig_word, cand.name)
                    else:
                        # Check synonyms (ONLY for action words, NOT materials)
                        if has_synonyms(sig_word) and WordWeightConfig._is_action_word(sig_word):
                            for syn in get_synonyms(sig_word):
                                if ' ' not in syn and syn in name_words_set:
                                    word_matched = True
                                    logger.debug("SYNONYM MATCH: '%s' (for '%s') found in '%s'", 
                                               syn, sig_word, cand.name)
                                    break
                    
                    # Fuzzy match (for typos) - stricter threshold
                    if not word_matched and len(sig_word) >= 4:
                        for name_word in name_words_set:
                            if len(name_word) >= 4:
                                similarity = difflib.SequenceMatcher(None, sig_word, name_word).ratio()
                                if similarity >= 0.85:  # Stricter threshold
                                    word_matched = True
                                    logger.debug("FUZZY MATCH: '%s' ≈ '%s' (%.2f) in '%s'", 
                                               sig_word, name_word, similarity, cand.name)
                                    break
                    
                    if word_matched:
                        matched_count += 1
                
                # Need ALL significant words to match
                if matched_count >= len(significant_words):
                    filtered.append(cand)
                    logger.debug("CANDIDATE ACCEPTED: '%s' (matched %d/%d words)", 
                               cand.name, matched_count, len(significant_words))
            
            if filtered:
                logger.info("Multi-word filter (compound-aware): %d → %d candidates matching ALL words %s", 
                            len(all_candidates), len(filtered), significant_words)
                return filtered
            else:
                # FALLBACK: Only for material-based queries
                logger.debug("ALL-word filter returned 0, checking if fallback appropriate...")
                
                # Fallback ONLY if query has material words (not for generic action-only queries)
                if has_material:
                    logger.debug("Material query detected, trying ANY-material fallback...")
                    filtered = []
                    for cand in all_candidates:
                        norm_name = _norm_name(cand.name)
                        name_words_set = set(norm_name.split())
                        
                        # Check if ANY material word matches (with compounds)
                        for sig_word in significant_words:
                            # Skip action words in fallback - only match materials
                            if WordWeightConfig._is_action_word(sig_word):
                                continue
                            
                            # Check compound
                            if sig_word in detected_compounds:
                                if self._candidate_contains_compound(norm_name, sig_word, detected_compounds[sig_word]):
                                    filtered.append(cand)
                                    logger.debug("FALLBACK COMPOUND MATCH: '%s' in '%s'", sig_word, cand.name)
                                    break
                            
                            # Check regular material word
                            if sig_word in name_words_set:
                                filtered.append(cand)
                                logger.debug("FALLBACK MATERIAL MATCH: '%s' in '%s'", sig_word, cand.name)
                                break
                    
                    if filtered:
                        logger.info("Multi-word filter (ANY-material fallback): %d → %d candidates", 
                                  len(all_candidates), len(filtered))
                        return filtered
                
                logger.info("No appropriate fallback available, returning empty candidates")
                return []
        
        # Single material word query but also has action word
        elif material_words:
            logger.debug("Material + other words: %s → MATERIAL FILTER", material_words)
            all_candidates = self._repository.get_all_ahs()
            filtered = [
                c for c in all_candidates 
                if any(mat_word in _norm_name(c.name).split() for mat_word in material_words)
            ]
            
            if filtered:
                logger.info("Material-mode: %d → %d candidates containing material words",
                           len(all_candidates), len(filtered))
                return filtered
        
        # For non-material multi-word queries, use head token + synonym expansion
        candidates = self._repository.by_name_candidates(head)
        logger.debug("Direct '%s' → %d candidates", head, len(candidates))
        
        # SYNONYM EXPANSION
        synonyms_to_search = set()
        
        if has_synonyms(head):
            manual = get_synonyms(head)
            synonyms_to_search.update(manual)
            logger.debug("+ %d manual synonyms", len(manual))
        
        if self._synonym_expander and self._synonym_expander.is_available():
            try:
                embedding = self._synonym_expander.expand_with_manual(head)
                synonyms_to_search.update(embedding)
                logger.debug("+ embedding synonyms (total now: %d)", len(synonyms_to_search))
            except Exception as e:
                logger.warning("Embedding expansion failed: %s", e)
        
        for synonym in synonyms_to_search:
            syn_candidates = self._repository.by_name_candidates(synonym)
            candidates.extend(syn_candidates)
            if syn_candidates:
                logger.debug("'%s' → +%d candidates", synonym, len(syn_candidates))
        
        # Deduplicate
        seen = set()
        unique = []
        for c in candidates:
            if c.id not in seen:
                seen.add(c.id)
                unique.append(c)
        candidates = unique
        logger.debug("After dedup: %d unique candidates", len(candidates))
        
        if not candidates:
            logger.debug("No candidates → fallback to all AHS")
            candidates = self._repository.get_all_ahs()
        
        logger.info("CandidateProvider returned %d candidates", len(candidates))
        return candidates
    
    def _detect_compound_materials_in_input(self, normalized_input: str) -> dict:
        """Detect which compound materials are present in the input.
        
        Only detects materials that are explicitly defined in COMPOUND_MATERIALS.
        
        Returns:
            Dict mapping detected material → list of compound phrase variants
            Example: {'hebel': ['bata ringan']}
        """
        detected = {}
        input_words = set(normalized_input.split())
        
        for material, variants in self._compound_materials.items():
            # For single-word materials (e.g., 'hebel')
            if ' ' not in material:
                if material in input_words:
                    detected[material] = variants
                    logger.debug("Detected compound material '%s' with variants: %s", material, variants)
            else:
                # For multi-word materials (e.g., 'bata ringan')
                # Check if the full phrase appears
                if material in normalized_input:
                    # Add both words as keys
                    words = material.split()
                    for word in words:
                        detected[word] = [material]
                        logger.debug("Detected compound material part '%s' from phrase '%s'", word, material)
        
        return detected
    
    def _candidate_contains_compound(self, candidate_name: str, material: str, compound_phrases: list) -> bool:
        """Check if candidate contains the material or its compound phrase variants.
        
        Args:
            candidate_name: Normalized candidate name
            material: The material word (e.g., 'hebel')
            compound_phrases: List of compound variants (e.g., ['bata ringan'])
        
        Returns:
            True if material OR any compound phrase is found in candidate
        """
        norm_name = _norm_name(candidate_name)
        
        # Check for exact material word
        if material in norm_name.split():
            return True
        
        # Check for compound phrases (as multi-word sequences)
        for phrase in compound_phrases:
            if phrase in norm_name:
                logger.debug("Found compound phrase '%s' in candidate '%s'", phrase, candidate_name)
                return True
        
        return False

class MatchingProcessor:
    def __init__(self, similarity_calculator: SimilarityCalculator, candidate_provider: CandidateProvider, min_similarity: float = 0.6):
        self._similarity_calculator = similarity_calculator
        self._candidate_provider = candidate_provider
        self._min_similarity = max(0.0, min(1.0, min_similarity))
    
    def find_best_match(self, query: str) -> Optional[dict]:
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
            seq_score = self._similarity_calculator.calculate_sequence_similarity(normalized_query, candidate_name)
            partial_score = self._similarity_calculator.calculate_partial_similarity(normalized_query, candidate_name)
            similarity_score = max(seq_score, partial_score)
            if similarity_score >= self._min_similarity and similarity_score > best_score:
                best_score = similarity_score
                best_match = {"source": "ahs", "id": candidate.id, "code": candidate.code, "name": candidate.name, "matched_on": "name"}
        logger.info("Best fuzzy match score=%.4f", best_score)
        return best_match
    
    def find_multiple_matches(self, query: str, limit: int = 5) -> List[dict]:
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
                match_result = {"source": "ahs", "id": candidate.id, "code": candidate.code, "name": candidate.name, "matched_on": "name", "_internal_score": similarity_score}
                matches.append((similarity_score, match_result))
        matches.sort(key=lambda x: x[0], reverse=True)
        logger.info("Multiple fuzzy matches found=%d", len(matches))
        return [match[1] for match in matches[:limit]]

class FuzzyMatcher:
    def __init__(self, repo: AhsRepository, min_similarity: float = 0.6, scorer: ConfidenceScorer | None = None, synonym_expander: SynonymExpander = None):
        self.repo = repo
        self.min_similarity = max(0.0, min(1.0, min_similarity))
        self.scorer: ConfidenceScorer = scorer or FuzzyConfidenceScorer()
        self._similarity_calculator = SimilarityCalculator(WordWeightConfig())
        self._candidate_provider = CandidateProvider(repo, synonym_expander)
        self._matching_processor = MatchingProcessor(self._similarity_calculator, self._candidate_provider, min_similarity)

    def match(self, description: str) -> Optional[dict]:
        logger.debug("FuzzyMatcher.match called with description=%r", description)
        if not description:
            return None
        return self._matching_processor.find_best_match(description.strip())

    def find_multiple_matches(self, description: str, limit: int = 5) -> List[dict]:
        logger.debug("FuzzyMatcher.find_multiple_matches called with description=%r", description)
        if not description or limit <= 0:
            return []
        return self._matching_processor.find_multiple_matches(description.strip(), limit)

    def match_with_confidence(self, description: str) -> Optional[dict]:
        logger.debug("FuzzyMatcher.match_with_confidence called with description=%r", description)
        if not description:
            return None
        normalized_query = _norm_name(description.strip())
        if not normalized_query:
            return None
        
        # Apply compound material expansion for scoring
        expanded_query = self._expand_query_for_scoring(normalized_query)
        logger.info("Query for scoring: '%s' → '%s'", normalized_query, expanded_query)
        
        candidates = self._candidate_provider.get_candidates_by_head_token(normalized_query)
        best = None
        best_conf = 0.0
        
        for cand in candidates:
            norm_cand = _norm_name(cand.name)
            if not norm_cand:
                continue
            
            # Score with both original and expanded query
            conf_original = self.scorer.score(normalized_query, norm_cand)
            conf_expanded = self.scorer.score(expanded_query, norm_cand) if expanded_query != normalized_query else 0.0
            conf = max(conf_original, conf_expanded)
            
            logger.debug("Confidence vs %r: orig=%.4f, expanded=%.4f, final=%.4f", 
                        cand.name, conf_original, conf_expanded, conf)
            
            if conf >= self.min_similarity and conf > best_conf:
                best_conf = conf
                best = cand
        
        if best:
            logger.info("Best confidence match id=%s score=%.4f", best.id, best_conf)
            return {"source": "ahs", "id": best.id, "code": best.code, "name": best.name, "matched_on": "name", "confidence": round(best_conf, 4)}
        logger.info("No confident match found for query=%r", description)
        return None

    def find_multiple_matches_with_confidence(self, description: str, limit: int = 5) -> List[dict]:
        logger.debug("FuzzyMatcher.find_multiple_matches_with_confidence called (limit=%d) desc=%r", limit, description)
        if not description or limit <= 0:
            return []
        normalized_query = _norm_name(description.strip())
        if not normalized_query:
            return []
        
        # Apply compound material expansion for scoring
        expanded_query = self._expand_query_for_scoring(normalized_query)
        logger.info("Query for scoring: '%s' → '%s'", normalized_query, expanded_query)
        
        candidates = self._candidate_provider.get_candidates_by_head_token(normalized_query)
        results = []
        
        for cand in candidates:
            norm_cand = _norm_name(cand.name)
            if not norm_cand:
                continue
            
            # Score with both original and expanded query
            conf_original = self.scorer.score(normalized_query, norm_cand)
            conf_expanded = self.scorer.score(expanded_query, norm_cand) if expanded_query != normalized_query else 0.0
            conf = max(conf_original, conf_expanded)
            
            logger.debug("Confidence vs %r: orig=%.4f, expanded=%.4f, final=%.4f", 
                        cand.name, conf_original, conf_expanded, conf)
            
            if conf >= self.min_similarity:
                results.append((conf, {"source": "ahs", "id": cand.id, "code": cand.code, "name": cand.name, "matched_on": "name", "confidence": round(conf, 4)}))
        
        results.sort(key=lambda x: x[0], reverse=True)
        logger.info("Found %d matches with confidence >= %.2f", len(results), self.min_similarity)
        return [result[1] for result in results[:limit]]
    
    def _expand_query_for_scoring(self, normalized_query: str) -> str:
        """Expand query by replacing compound materials and action words.
        
        Example: 
            "pemasangan hebel" → "pemasangan bata ringan"
            "pekerjaan keramik" → "pemasangan keramik"
        """
        words = normalized_query.split()
        expanded_words = []
        compound_materials = get_compound_materials()
        
        for word in words:
            # Replace action words with first synonym
            if has_synonyms(word) and not is_compound_material(word):
                syns = get_synonyms(word)
                if syns:
                    expanded_words.append(syns[0])
                    logger.debug("Expanded action '%s' → '%s'", word, syns[0])
                    continue
            
            # Replace compound materials with first variant
            if word in compound_materials:
                variants = compound_materials[word]
                if variants:
                    # Use first variant (most common)
                    expanded_words.append(variants[0])
                    logger.debug("Expanded compound '%s' → '%s'", word, variants[0])
                    continue
            
            # Keep original word
            expanded_words.append(word)
        
        return ' '.join(expanded_words)

    def _calculate_partial_similarity(self, text1: str, text2: str) -> float:
        logger.debug("Backward partial similarity between %r and %r", text1, text2)
        return self._similarity_calculator.calculate_partial_similarity(text1, text2)

    def _calculate_confidence_score(self, norm_query: str, norm_candidate: str) -> float:
        logger.debug("Backward confidence score between %r and %r", norm_query, norm_candidate)
        return self.scorer.score(norm_query, norm_candidate)

    def _fuzzy_match_name(self, raw_input: str) -> Optional[dict]:
        logger.debug("Legacy _fuzzy_match_name called with input=%r", raw_input)
        return self.match(raw_input)

    def _get_multiple_name_matches(self, raw_input: str, limit: int) -> List[dict]:
        logger.debug("Legacy _get_multiple_name_matches called with input=%r limit=%d", raw_input, limit)
        return self.find_multiple_matches(raw_input, limit)

    def _fuzzy_match_name_with_confidence(self, raw_input: str) -> Optional[dict]:
       logger.debug("Legacy _fuzzy_match_name_with_confidence called with input=%r", raw_input)
       return self.match_with_confidence(raw_input)

    def _get_multiple_name_matches_with_confidence(self, raw_input: str, limit: int) -> List[dict]:
        logger.debug("Legacy _get_multiple_name_matches_with_confidence called with input=%r limit=%d", raw_input, limit)
        return self.find_multiple_matches_with_confidence(raw_input, limit)