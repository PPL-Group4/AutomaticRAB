import logging
from typing import List, Optional, Set
import numpy as np
from sentence_transformers import SentenceTransformer, util

from automatic_job_matching.repository.ahs_repo import DbAhsRepository
from automatic_job_matching.utils.text_normalizer import normalize_text
from automatic_job_matching.config.action_synonyms import get_synonyms, has_synonyms

logger = logging.getLogger(__name__)

class SynonymExpander:
    """Expands query words using word embeddings to find semantically similar terms."""
    
    def __init__(self, model_name: str = "firqaaa/indo-sentence-bert-base", similarity_threshold: float = 0.7):
        try:
            self.model = SentenceTransformer(model_name)
            self.threshold = similarity_threshold
            self._available = True
            logger.info("SynonymExpander initialized with model: %s", model_name)
        except Exception as e:
            logger.warning("Failed to load embedding model: %s. SynonymExpander disabled.", e)
            self.model = None
            self._available = False
    
    def is_available(self) -> bool:
        """Check if the synonym expander is available."""
        return self._available
    
    def expand(self, word: str, candidate_words: List[str], limit: int = 3) -> Set[str]:
        """
        Find semantically similar words from candidate list.
        
        Args:
            word: The input word to expand
            candidate_words: List of potential synonyms to compare against
            limit: Maximum number of synonyms to return
            
        Returns:
            Set of similar words
        """
        if not self._available or not word or not candidate_words:
            return set()
        
        # Handle edge case: limit <= 0
        if limit <= 0:
            return set()
        
        try:
            # Encode the query word
            word_embedding = self.model.encode(word, convert_to_tensor=True)
            
            # Encode candidate words
            candidate_embeddings = self.model.encode(candidate_words, convert_to_tensor=True)
            
            # Calculate similarities
            similarities = util.cos_sim(word_embedding, candidate_embeddings)[0]
            
            # Get top similar words above threshold
            similar_words = set()
            for idx, score in enumerate(similarities):
                if score.item() >= self.threshold and candidate_words[idx] != word:
                    similar_words.add(candidate_words[idx])
                    if len(similar_words) >= limit:
                        break
            
            logger.debug("Expanded '%s' to %d similar words: %s", word, len(similar_words), similar_words)
            return similar_words
            
        except Exception as e:
            logger.warning("Synonym expansion failed for '%s': %s", word, e)
            return set()
    
    def expand_with_manual(self, word: str, candidate_words: List[str] = None, limit: int = 3) -> Set[str]:
        """
        Expand word using both manual synonyms and embeddings.
        
        Args:
            word: The input word to expand
            candidate_words: Optional list of candidates (if None, only manual synonyms used)
            limit: Maximum number of embedding-based synonyms to return
            
        Returns:
            Combined set of manual and embedding-based synonyms
        """
        synonyms = set()
        
        # Add manual synonyms first
        if has_synonyms(word):
            manual = get_synonyms(word)
            synonyms.update(manual)
            logger.debug("Added %d manual synonyms for '%s'", len(manual), word)
        
        # Add embedding-based synonyms if available
        if self._available and candidate_words:
            embedding_syns = self.expand(word, candidate_words, limit)
            synonyms.update(embedding_syns)
            logger.debug("Added %d embedding synonyms for '%s'", len(embedding_syns), word)
        
        return synonyms


class SemanticMatcher:
    """AI-powered semantic matching using sentence embeddings."""
    
    def __init__(self, repo: DbAhsRepository, model_name: str = "firqaaa/indo-sentence-bert-base"):
        self.repo = repo
        self.model = SentenceTransformer(model_name)
        self._cache = {}  # Cache embeddings for performance
        logger.info("SemanticMatcher initialized with model: %s", model_name)
    
    def find_best_match(self, query: str, min_similarity: float = 0.5) -> Optional[dict]:
        """Find single best semantic match."""
        matches = self.find_multiple_matches(query, limit=1, min_similarity=min_similarity)
        return matches[0] if matches else None
    
    def find_multiple_matches(self, query: str, limit: int = 5, min_similarity: float = 0.5) -> List[dict]:
        """Find top-k semantic matches using cosine similarity."""
        
        normalized_query = normalize_text(query)
        if not normalized_query:
            return []
        
        logger.info("Semantic search for: %s (min_sim=%.2f)", normalized_query, min_similarity)
        
        # Get all candidates
        all_candidates = self.repo.get_all_ahs()
        
        # Early return if no candidates
        if not all_candidates:
            logger.warning("No candidates found in repository")
            return []
        
        logger.debug("Encoding %d candidates...", len(all_candidates))
        
        # Encode query
        query_embedding = self._encode_query(normalized_query)
        if query_embedding is None:
            return []
        
        # Encode candidates (with caching)
        candidate_embeddings, candidate_objects = self._encode_candidates(all_candidates)
        
        # Early return if no valid candidates after encoding
        if not candidate_embeddings:
            logger.warning("No valid candidates after encoding")
            return []
        
        # Calculate similarities and get results
        results = self._calculate_and_rank_matches(
            query_embedding, 
            candidate_embeddings, 
            candidate_objects, 
            limit, 
            min_similarity
        )
        
        logger.info("Semantic matching found %d results", len(results))
        return results
    
    def _encode_query(self, normalized_query: str):
        """Encode query string into embedding."""
        try:
            return self.model.encode(normalized_query, convert_to_tensor=True)
        except Exception as e:
            logger.error("Failed to encode query: %s", e)
            return None
    
    def _encode_candidates(self, all_candidates: List) -> tuple:
        """Encode all candidates with caching."""
        candidate_embeddings = []
        candidate_objects = []
        
        for cand in all_candidates:
            norm_name = normalize_text(cand.name)
            if not norm_name:
                continue
            
            # Check cache
            if norm_name not in self._cache:
                embedding = self._encode_single_candidate(norm_name)
                if embedding is None:
                    continue
                self._cache[norm_name] = embedding
            
            candidate_embeddings.append(self._cache[norm_name])
            candidate_objects.append(cand)
        
        return candidate_embeddings, candidate_objects
    
    def _encode_single_candidate(self, norm_name: str):
        """Encode a single candidate name."""
        try:
            return self.model.encode(norm_name, convert_to_tensor=True)
        except Exception as e:
            logger.warning("Failed to encode candidate '%s': %s", norm_name, e)
            return None
    
    def _calculate_and_rank_matches(
        self, 
        query_embedding, 
        candidate_embeddings: List, 
        candidate_objects: List, 
        limit: int, 
        min_similarity: float
    ) -> List[dict]:
        """Calculate similarities and rank matches."""
        # Calculate cosine similarities
        try:
            similarities = util.cos_sim(query_embedding, candidate_embeddings)[0]
        except Exception as e:
            logger.error("Failed to calculate similarities: %s", e)
            return []
        
        # Sort by similarity
        top_indices = similarities.argsort(descending=True)
        
        return self._build_results(
            top_indices, 
            similarities, 
            candidate_objects, 
            limit, 
            min_similarity
        )
    
    def _build_results(
        self, 
        top_indices, 
        similarities, 
        candidate_objects: List, 
        limit: int, 
        min_similarity: float
    ) -> List[dict]:
        """Build result list from top matches."""
        results = []
        
        for idx in top_indices[:limit * 2]:  # Get 2x to filter by threshold
            idx = idx.item()
            score = similarities[idx].item()
            
            if score < min_similarity:
                break
            
            cand = candidate_objects[idx]
            results.append({
                "source": "ahs",
                "id": cand.id,
                "code": cand.code,
                "name": cand.name,
                "matched_on": "semantic",
                "confidence": round(score, 4)
            })
            
            if len(results) >= limit:
                break
        
        return results