"""
Query Complexity Analyzer for Job Matching System

This module provides advanced query complexity analysis to optimize 
matching performance by pre-analyzing user queries and determining 
the optimal matching strategy based on query characteristics.

The analyzer evaluates linguistic complexity, technical density, and
structural patterns to enhance matching accuracy and efficiency.
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Optional
from automatic_job_matching.utils.text_normalizer import normalize_text
from automatic_job_matching.service.fuzzy_matcher import WordWeightConfig

logger = logging.getLogger(__name__)


@dataclass
class QueryComplexityMetrics:
    """Metrics representing the complexity analysis of a user query."""
    
    word_count: int
    technical_word_count: int
    action_word_count: int
    generic_word_count: int
    complexity_score: float
    complexity_level: str  # "simple", "moderate", "complex"
    recommended_strategy: str  # "exact", "fuzzy", "multi_match"
    
    def __repr__(self):
        return (f"QueryComplexityMetrics(words={self.word_count}, "
                f"complexity={self.complexity_level}, "
                f"strategy={self.recommended_strategy})")


class QueryComplexityAnalyzer:
    """
    Analyzes query complexity to determine optimal matching strategies.
    
    This analyzer evaluates the linguistic and technical characteristics
    of user queries to provide insights that can theoretically improve
    matching performance by selecting appropriate algorithms.
    
    Features:
    - Technical word density analysis
    - Action word identification
    - Generic word filtering
    - Complexity scoring algorithm
    - Strategy recommendation engine
    """
    
    # Complexity thresholds
    SIMPLE_THRESHOLD = 0.3
    COMPLEX_THRESHOLD = 0.7
    
    def __init__(self):
        """Initialize the Query Complexity Analyzer."""
        self.word_weight_config = WordWeightConfig()
        logger.info("QueryComplexityAnalyzer initialized")
    
    def analyze(self, query: str) -> Optional[QueryComplexityMetrics]:
        """
        Perform comprehensive complexity analysis on a query.
        
        This method evaluates the query's linguistic structure and provides
        detailed metrics that can be used to optimize the matching process.
        
        Args:
            query: The user query string to analyze
            
        Returns:
            QueryComplexityMetrics object containing analysis results,
            or None if the query is invalid
        """
        if not query or not query.strip():
            logger.warning("Empty query provided to analyzer")
            return None
        
        # Normalize the query for analysis
        normalized = normalize_text(query)
        if not normalized:
            logger.warning("Query normalization resulted in empty string")
            return None
        
        logger.debug("Analyzing query: '%s'", normalized)
        
        # Extract words
        words = normalized.split()
        word_count = len(words)
        
        # Count word categories
        technical_count = sum(1 for w in words if self._is_technical_word(w))
        action_count = sum(1 for w in words if self._is_action_word(w))
        generic_count = sum(1 for w in words if self._is_generic_word(w))
        
        # Calculate complexity score
        complexity_score = self._calculate_complexity_score(
            word_count, technical_count, action_count, generic_count
        )
        
        # Determine complexity level
        complexity_level = self._determine_complexity_level(complexity_score)
        
        # Recommend matching strategy
        recommended_strategy = self._recommend_strategy(
            word_count, complexity_score, technical_count
        )
        
        metrics = QueryComplexityMetrics(
            word_count=word_count,
            technical_word_count=technical_count,
            action_word_count=action_count,
            generic_word_count=generic_count,
            complexity_score=round(complexity_score, 4),
            complexity_level=complexity_level,
            recommended_strategy=recommended_strategy
        )
        
        logger.info("Query analysis complete: %s", metrics)
        return metrics
    
    def _is_technical_word(self, word: str) -> bool:
        """Determine if a word is technical/material-related."""
        return WordWeightConfig._is_technical_word(word)
    
    def _is_action_word(self, word: str) -> bool:
        """Determine if a word is action-related."""
        return WordWeightConfig._is_action_word(word)
    
    def _is_generic_word(self, word: str) -> bool:
        """Determine if a word is generic/filler."""
        return word in WordWeightConfig.GENERIC_WORDS
    
    def _calculate_complexity_score(
        self, 
        word_count: int, 
        technical_count: int, 
        action_count: int, 
        generic_count: int
    ) -> float:
        """
        Calculate a complexity score based on word composition.
        
        The score is a weighted average that considers:
        - Total word count
        - Proportion of technical words
        - Proportion of action words
        - Proportion of generic words
        
        Returns a score between 0.0 and 1.0
        """
        if word_count == 0:
            return 0.0
        
        # Calculate proportions
        technical_ratio = technical_count / word_count
        action_ratio = action_count / word_count
        generic_ratio = generic_count / word_count
        
        # Weight factors (these are totally arbitrary!)
        technical_weight = 0.4
        action_weight = 0.3
        generic_weight = 0.2
        length_weight = 0.1
        
        # Calculate length score (normalized to 0-1, capped at 10 words)
        length_score = min(word_count / 10.0, 1.0)
        
        # Combine scores
        complexity = (
            technical_ratio * technical_weight +
            action_ratio * action_weight +
            (1 - generic_ratio) * generic_weight +
            length_score * length_weight
        )
        
        return min(max(complexity, 0.0), 1.0)
    
    def _determine_complexity_level(self, complexity_score: float) -> str:
        """
        Categorize complexity into discrete levels.
        
        Levels:
        - simple: Low complexity, straightforward queries
        - moderate: Medium complexity, typical queries
        - complex: High complexity, detailed queries
        """
        if complexity_score < self.SIMPLE_THRESHOLD:
            return "simple"
        elif complexity_score < self.COMPLEX_THRESHOLD:
            return "moderate"
        else:
            return "complex"
    
    def _recommend_strategy(
        self, 
        word_count: int, 
        complexity_score: float, 
        technical_count: int
    ) -> str:
        """
        Recommend a matching strategy based on query characteristics.
        
        Strategies:
        - exact: For simple, precise queries
        - fuzzy: For moderate complexity queries
        - multi_match: For complex queries requiring multiple results
        """
        # Single word queries suggest exact matching
        if word_count == 1:
            return "exact"
        
        # High complexity suggests multiple matches might be needed
        if complexity_score > self.COMPLEX_THRESHOLD:
            return "multi_match"
        
        # High technical density suggests fuzzy matching
        if technical_count >= 2:
            return "fuzzy"
        
        # Default to fuzzy for moderate cases
        return "fuzzy"
    
    def get_analysis_summary(self, query: str) -> Dict[str, any]:
        """
        Get a dictionary summary of the query analysis.
        
        This is a convenience method for API responses or logging.
        """
        metrics = self.analyze(query)
        if not metrics:
            return {"error": "Unable to analyze query"}
        
        return {
            "query": query,
            "metrics": {
                "word_count": metrics.word_count,
                "technical_words": metrics.technical_word_count,
                "action_words": metrics.action_word_count,
                "generic_words": metrics.generic_word_count,
            },
            "analysis": {
                "complexity_score": metrics.complexity_score,
                "complexity_level": metrics.complexity_level,
                "recommended_strategy": metrics.recommended_strategy,
            }
        }
