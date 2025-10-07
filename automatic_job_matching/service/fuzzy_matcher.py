from __future__ import annotations
from dataclasses import dataclass
from typing import List, Protocol, Optional
import difflib
import logging
import re

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

class WordWeightConfig:
    """Dynamic word weight configuration based on AHSP construction database patterns."""
    
    HIGH_WEIGHT = 3.0
    NORMAL_WEIGHT = 1.0
    LOW_WEIGHT = 0.3
    ULTRA_LOW_WEIGHT = 0.15
    
    # ========== ACTION WORD PATTERNS (from CSV analysis) ==========
    ACTION_PATTERNS = [
        # Common prefixes
        r'^pe[mr]',              # pemasangan, pembongkaran, perbaikan
        r'^pen[yg]?',            # penggalian, pengecatan, penyelesaian
        r'^di',                  # passive voice
        
        # Suffix patterns  
        r'an$',                  # pekerjaan, pemasangan, galian, urugan
        r'kan$',                 # pasangkan
        
        # Specific action roots from your CSV
        r'^(pasang|bongkar|ganti|bangun|renovasi|perbaik|buat|install)',
        r'^(galian|urugan|pemadatan|pembuangan|pengangkutan)',
        r'^(pengukuran|pengecatan|pelituran|pemolesan|finishing)',
        r'^(plester|acian|grouting|curing|ereksi|fabrikasi)',
    ]
    
    # ========== GENERIC/STOPWORDS ==========
    GENERIC_WORDS = {
        'untuk', 'dan', 'atau', 'dengan', 'pada', 'di', 'ke', 'dari', 
        'yang', 'ini', 'itu', 'tersebut', 'sebagai', 'antara', 'oleh',
        'dalam', 'luar', 'atas', 'bawah', 'semua', 'beberapa',
        'cara', 'secara', 'tiap', 'per', 'setiap', 'hingga', 'sampai',
        'volume', 'ukuran', 'lebar', 'tinggi',
    }
    
    # ========== TECHNICAL/MATERIAL INDICATORS (from your CSV) ==========
    TECHNICAL_INDICATORS = {
        # === PRIMARY MATERIALS (very common in your CSV) ===
        'keramik', 'beton', 'semen', 'besi', 'baja', 'kayu', 'aluminium', 
        'pvc', 'gypsum', 'granit', 'marmer', 'kaca', 'aspal',
        
        # === BUILDING MATERIALS ===
        'hollow', 'batako', 'hebel', 'conblock', 'roster', 'rooster',
        'triplek', 'multiplek', 'plywood', 'partikel', 'mdf',
        'tegel', 'teraso', 'homogeneous', 'porselen', 'teralux',
        
        # === STRUCTURAL COMPONENTS ===
        'pipa', 'kabel', 'balok', 'kolom', 'sloof', 'pondasi', 'rangka',
        'dinding', 'lantai', 'atap', 'genteng', 'pintu', 'jendela',
        'tangga', 'railing', 'pagar', 'kanopi', 'plafon', 'ceiling',
        'bekisting', 'tulangan', 'wiremesh', 'angkur', 'baut',
        
        # === METAL & COMPOSITES ===
        'logam', 'stainless', 'galvanis', 'tembaga', 'kuningan', 'seng',
        'fiber', 'fiberglass', 'composite', 'resin', 'epoxy',
        
        # === SYSTEMS & INSTALLATIONS ===
        'listrik', 'plumbing', 'sanitasi', 'drainase', 'septic', 'ac',
        'lift', 'elevator', 'ventilasi', 'exhaust', 'hydrant', 'sprinkler',
        
        # === FINISHING MATERIALS ===
        'cat', 'wallpaper', 'vinyl', 'karpet', 'parket', 'laminate',
        'nat', 'grout', 'menie', 'vernis', 'pelitur', 'plamir',
        
        # === AGGREGATES ===
        'pasir', 'kerikil', 'sirtu', 'makadam', 'split', 'batu', 'cor',
        
        # === SANITAIR ===
        'wastafel', 'closet', 'kloset', 'urinoir', 'bathup', 'shower',
        'kran', 'floor', 'drain',
        
        # === DOORS & WINDOWS ===
        'kusen', 'daun', 'engsel', 'kunci', 'handle', 'grendel',
        'jalusi', 'rolling', 'lipat',
        
        # === MEASUREMENTS (strong technical signal) ===
        'meter', 'cm', 'mm', 'inch', 'm2', 'm3', 'kg', 'ton', 'liter',
        'diameter', 'tebal', 'panjang', 'dimensi', 'kapasitas',
        
        # === PLANTS/LANDSCAPING (from your CSV section 4) ===
        'pohon', 'palem', 'semak', 'rumput', 'tanaman', 'penutup',
        'polybag', 'pupuk', 'organik', 'anorganik',
        
        # === TECHNICAL SPECS ===
        'mutu', 'kualitas', 'standar', 'spesifikasi', 'grade', 'class',
        'mpa', 'sni', 'iso', 'astm',
    }
    
    @classmethod
    def get_word_weight(cls, word: str) -> float:
        """Dynamically calculate word weight based on rules."""
        word_lower = word.lower()
        
        # Rule 1: Stopwords get ultra-low weight
        if word_lower in cls.GENERIC_WORDS:
            return cls.ULTRA_LOW_WEIGHT
        
        # Rule 2: Action patterns get low weight
        if cls._is_action_word(word_lower):
            return cls.LOW_WEIGHT
        
        # Rule 3: Technical/material words get high weight
        if cls._is_technical_word(word_lower):
            return cls.HIGH_WEIGHT
        
        # Rule 4: Numbers indicate technical context (dimensions, specs)
        if re.search(r'\d', word_lower):
            return cls.HIGH_WEIGHT * 0.9
        
        # Rule 5: Very short words (<=2 chars) are likely abbreviations or generic
        if len(word_lower) <= 2:
            return cls.ULTRA_LOW_WEIGHT
        
        # Rule 6: Length-based heuristic (longer = more specific)
        if len(word_lower) >= 10:
            return cls.NORMAL_WEIGHT * 1.3
        elif len(word_lower) >= 7:
            return cls.NORMAL_WEIGHT * 1.1
        elif len(word_lower) <= 3:
            return cls.NORMAL_WEIGHT * 0.8
        
        return cls.NORMAL_WEIGHT
    
    @classmethod
    def _is_action_word(cls, word: str) -> bool:
        """Check if word matches action patterns."""
        for pattern in cls.ACTION_PATTERNS:
            if re.search(pattern, word):
                return True
        return False
    
    @classmethod
    def _is_technical_word(cls, word: str) -> bool:
        """Check if word is technical/material term."""
        # Direct match
        if word in cls.TECHNICAL_INDICATORS:
            return True
        
        # Contains technical indicator as substring (for compound words)
        # e.g., "keramik30x30", "pipa3/4"
        for indicator in cls.TECHNICAL_INDICATORS:
            if len(indicator) >= 4 and indicator in word:
                return True
        
        return False

# SimilarityCalculator stays exactly the same
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
    def __init__(self, repo: AhsRepository, min_similarity: float = 0.6, scorer: ConfidenceScorer | None = None):
        self.repo = repo
        self.min_similarity = max(0.0, min(1.0, min_similarity))
        self.scorer: ConfidenceScorer = scorer or FuzzyConfidenceScorer()
        self._similarity_calculator = SimilarityCalculator(WordWeightConfig())
        self._candidate_provider = CandidateProvider(repo)
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
        candidates = self._candidate_provider.get_candidates_by_head_token(normalized_query)
        results = []
        for cand in candidates:
            norm_cand = _norm_name(cand.name)
            if not norm_cand:
                continue
            conf = self.scorer.score(normalized_query, norm_cand)
            logger.debug("Confidence score vs candidate %r = %.4f", cand.name, conf)
            if conf >= self.min_similarity:
                results.append((conf, {"source": "ahs", "id": cand.id, "code": cand.code, "name": cand.name, "matched_on": "name", "confidence": round(conf, 4)}))
        results.sort(key=lambda x: x[0], reverse=True)
        logger.info("Found %d matches with confidence >= %.2f", len(results), self.min_similarity)
        return [result[1] for result in results[:limit]]

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
