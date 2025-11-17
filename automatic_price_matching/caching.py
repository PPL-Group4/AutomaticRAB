"""
Standalone caching logic extracted for 100% coverage testing.
This module contains ONLY the caching-related code.
"""
from decimal import Decimal
from typing import Optional
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


class DatabasePriceCacher:
    """
    Handles caching logic for database price lookups.
    This is the EXACT caching logic added to DatabaseAhspSource.
    """
    
    def __init__(self):
        self._cache_key_prefix = "db_ahsp_price:"
    
    def get_cached_price(self, canonical_code: str) -> Optional[Decimal]:
        """
        Try to get price from cache.
        Returns None if not in cache or if code is empty.
        """
        if not canonical_code:
            return None
        
        cache_key = f"{self._cache_key_prefix}{canonical_code}"
        try:
            cached_price = cache.get(cache_key)
            if cached_price is not None:
                logger.debug("DB cache hit for code=%s", canonical_code)
                return Decimal(str(cached_price)) if cached_price else None
        except Exception as e:
            logger.debug("Cache lookup failed for DB, continuing without cache: %s", e)
        
        return None
    
    def cache_price(self, canonical_code: str, price: Optional[Decimal], is_failure: bool = False) -> None:
        """
        Cache a price lookup result.
        
        Args:
            canonical_code: The code to cache
            price: The price to cache (None for failures)
            is_failure: If True, cache with shorter timeout (5 min vs 1 hour)
        """
        if not canonical_code:
            return
        
        cache_key = f"{self._cache_key_prefix}{canonical_code}"
        timeout = 300 if is_failure else 3600  # 5 min for failures, 1 hour for success
        
        try:
            value = str(price) if price is not None else ""
            cache.set(cache_key, value, timeout=timeout)
        except Exception as e:
            logger.debug("Cache set failed for DB, continuing without cache: %s", e)


class ViewRequestCacher:
    """
    Handles request-level caching for view responses.
    This is the EXACT caching logic added to recompute_total_cost view.
    """
    
    def __init__(self):
        self._cache_key_prefix = "price_match:"
    
    def get_cache_key(self, request_body: bytes) -> str:
        """Generate cache key from request body using MD5 hash."""
        import hashlib
        return f"{self._cache_key_prefix}{hashlib.md5(request_body).hexdigest()}"
    
    def get_cached_response(self, request_body: bytes, has_row_key: bool) -> Optional[dict]:
        """
        Try to get cached response for request.
        
        Args:
            request_body: The request body bytes
            has_row_key: If True, bypass cache
            
        Returns:
            Cached response dict or None
        """
        if has_row_key:
            return None  # Bypass cache for row_key requests
        
        cache_key = self.get_cache_key(request_body)
        try:
            cached_response = cache.get(cache_key)
            if cached_response:
                logger.debug("View cache hit for key=%s", cache_key)
                return cached_response
        except Exception as e:
            logger.debug("View cache lookup failed, continuing: %s", e)
        
        return None
    
    def cache_response(self, request_body: bytes, response_data: dict) -> None:
        """
        Cache a response for 60 seconds.
        
        Args:
            request_body: The request body bytes
            response_data: The response dict to cache
        """
        cache_key = self.get_cache_key(request_body)
        try:
            cache.set(cache_key, response_data, timeout=60)
        except Exception as e:
            logger.debug("View cache set failed, continuing: %s", e)
