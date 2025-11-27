import logging
from typing import List, Optional, Set
import numpy as np

# 🚫 Completely disable sentence-transformers for now.
# This prevents Django startup crashes (urllib3 SSL errors).
SentenceTransformer = None
util = None

from automatic_job_matching.repository.ahs_repo import DbAhsRepository
from automatic_job_matching.utils.text_normalizer import normalize_text
from automatic_job_matching.config.action_synonyms import get_synonyms, has_synonyms

logger = logging.getLogger(__name__)


# ============================================================
#  MANUAL-ONLY SYNONYM EXPANDER (SAFE MODE)
# ============================================================

class SynonymExpander:
    """
    SAFE MODE:
    - Only uses manual synonyms.
    - Embedding-based synonyms are completely disabled.
    """

    def __init__(self, model_name: str = "firqaaa/indo-sentence-bert-base",
                 similarity_threshold: float = 0.7):
        # Embeddings are disabled
        self.model = None
        self.threshold = similarity_threshold
        self._available = False  # Always false because sentence-transformers is disabled
        logger.warning("SynonymExpander running in SAFE MODE (no sentence-transformers).")

    def is_available(self) -> bool:
        return False   # Always false in safe mode

    def expand(self, word: str, candidate_words: List[str], limit: int = 3) -> Set[str]:
        """Embedding-based synonyms disabled."""
        return set()

    def expand_with_manual(self, word: str, candidate_words: List[str] = None, limit: int = 3) -> Set[str]:
        """Return ONLY manual synonyms."""
        synonyms = set()

        if has_synonyms(word):
            manual = get_synonyms(word)
            synonyms.update(manual)
            logger.debug("Manual-only synonyms for '%s': %s", word, manual)

        return synonyms


# ============================================================
#  SEMANTIC MATCHER (DISABLED IN SAFE MODE)
# ============================================================

class SemanticMatcher:
    """
    DISABLED:
    - All semantic matching features are turned off.
    - Calling this will return no results.
    """

    def __init__(self, repo: DbAhsRepository, model_name: str = "firqaaa/indo-sentence-bert-base"):
        self.repo = repo
        logger.warning("SemanticMatcher disabled (sentence-transformers not available).")

    def find_best_match(self, query: str, min_similarity: float = 0.5) -> Optional[dict]:
        return None

    def find_multiple_matches(self, query: str, limit: int = 5, min_similarity: float = 0.5) -> List[dict]:
        return []
