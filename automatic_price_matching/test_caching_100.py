"""
Tests for the caching module - achieving 100% coverage.
"""
from unittest.mock import patch, Mock
from django.test import TestCase
from django.core.cache import cache
from decimal import Decimal

from automatic_price_matching.caching import DatabasePriceCacher, ViewRequestCacher


class TestDatabasePriceCacher(TestCase):
    """Test database price caching - 100% coverage"""
    
    def setUp(self):
        cache.clear()
        self.cacher = DatabasePriceCacher()
    
    def tearDown(self):
        cache.clear()
    
    def test_empty_code_returns_none(self):
        """Test empty code returns None"""
        self.assertIsNone(self.cacher.get_cached_price(""))
        self.assertIsNone(self.cacher.get_cached_price(None))
    
    def test_cache_miss_returns_none(self):
        """Test cache miss returns None"""
        result = self.cacher.get_cached_price("NOTCACHED")
        self.assertIsNone(result)
    
    def test_cache_hit_returns_price(self):
        """Test cache hit returns cached price"""
        # Cache a price
        self.cacher.cache_price("TEST001", Decimal("100.50"))
        
        # Retrieve it
        result = self.cacher.get_cached_price("TEST001")
        self.assertEqual(result, Decimal("100.50"))
    
    def test_cache_empty_string_for_none_price(self):
        """Test None price is cached as empty string"""
        self.cacher.cache_price("NOTFOUND", None)
        
        # Should return None when retrieved
        result = self.cacher.get_cached_price("NOTFOUND")
        self.assertIsNone(result)
    
    def test_failure_caching_uses_short_timeout(self):
        """Test failure caching uses 5 minute timeout"""
        with patch.object(cache, 'set') as mock_set:
            self.cacher.cache_price("FAILED", None, is_failure=True)
            mock_set.assert_called_once()
            # Check timeout argument
            call_args = mock_set.call_args
            self.assertEqual(call_args.kwargs['timeout'], 300)  # 5 minutes
    
    def test_success_caching_uses_long_timeout(self):
        """Test success caching uses 1 hour timeout"""
        with patch.object(cache, 'set') as mock_set:
            self.cacher.cache_price("SUCCESS", Decimal("200.00"), is_failure=False)
            mock_set.assert_called_once()
            # Check timeout argument
            call_args = mock_set.call_args
            self.assertEqual(call_args.kwargs['timeout'], 3600)  # 1 hour
    
    @patch.object(cache, 'get')
    def test_cache_get_exception_returns_none(self, mock_get):
        """Test cache.get() exception is handled"""
        mock_get.side_effect = Exception("Cache error")
        
        result = self.cacher.get_cached_price("TEST")
        self.assertIsNone(result)
    
    @patch.object(cache, 'set')
    def test_cache_set_exception_continues(self, mock_set):
        """Test cache.set() exception doesn't raise"""
        mock_set.side_effect = Exception("Cache error")
        
        # Should not raise exception
        self.cacher.cache_price("TEST", Decimal("100.00"))
    
    def test_empty_code_cache_does_nothing(self):
        """Test caching empty code does nothing"""
        with patch.object(cache, 'set') as mock_set:
            self.cacher.cache_price("", Decimal("100.00"))
            mock_set.assert_not_called()
            
            self.cacher.cache_price(None, Decimal("100.00"))
            mock_set.assert_not_called()


class TestViewRequestCacher(TestCase):
    """Test view request caching - 100% coverage"""
    
    def setUp(self):
        cache.clear()
        self.cacher = ViewRequestCacher()
    
    def tearDown(self):
        cache.clear()
    
    def test_cache_key_generation(self):
        """Test cache key is generated from request body"""
        body = b'{"test": "data"}'
        key = self.cacher.get_cache_key(body)
        
        # Should start with prefix
        self.assertTrue(key.startswith("price_match:"))
        
        # Should be consistent
        key2 = self.cacher.get_cache_key(body)
        self.assertEqual(key, key2)
    
    def test_different_bodies_different_keys(self):
        """Test different bodies produce different keys"""
        key1 = self.cacher.get_cache_key(b'{"a": 1}')
        key2 = self.cacher.get_cache_key(b'{"a": 2}')
        self.assertNotEqual(key1, key2)
    
    def test_row_key_bypasses_cache(self):
        """Test requests with row_key bypass cache"""
        body = b'{"data": []}'
        
        # Cache something
        self.cacher.cache_response(body, {"result": "test"})
        
        # Try to get with row_key=True
        result = self.cacher.get_cached_response(body, has_row_key=True)
        self.assertIsNone(result)
    
    def test_cache_miss_returns_none(self):
        """Test cache miss returns None"""
        body = b'{"data": []}'
        result = self.cacher.get_cached_response(body, has_row_key=False)
        self.assertIsNone(result)
    
    def test_cache_hit_returns_response(self):
        """Test cache hit returns cached response"""
        body = b'{"data": []}'
        response = {"result": "success", "total": 100}
        
        # Cache it
        self.cacher.cache_response(body, response)
        
        # Retrieve it
        result = self.cacher.get_cached_response(body, has_row_key=False)
        self.assertEqual(result, response)
    
    def test_cache_uses_60_second_timeout(self):
        """Test response caching uses 60 second timeout"""
        with patch.object(cache, 'set') as mock_set:
            body = b'{"data": []}'
            self.cacher.cache_response(body, {"result": "test"})
            
            mock_set.assert_called_once()
            call_args = mock_set.call_args
            self.assertEqual(call_args.kwargs['timeout'], 60)
    
    @patch.object(cache, 'get')
    def test_cache_get_exception_returns_none(self, mock_get):
        """Test cache.get() exception is handled"""
        mock_get.side_effect = Exception("Cache error")
        
        body = b'{"data": []}'
        result = self.cacher.get_cached_response(body, has_row_key=False)
        self.assertIsNone(result)
    
    @patch.object(cache, 'set')
    def test_cache_set_exception_continues(self, mock_set):
        """Test cache.set() exception doesn't raise"""
        mock_set.side_effect = Exception("Cache error")
        
        body = b'{"data": []}'
        # Should not raise exception
        self.cacher.cache_response(body, {"result": "test"})
