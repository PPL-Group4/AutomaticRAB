from functools import lru_cache

@lru_cache(maxsize=5000)
def cache_match_description(desc: str):
    from .job_matcher import match_description
    return match_description(desc)

@lru_cache(maxsize=5000)
def cache_parse_decimal(val: str):
    from .reader import parse_decimal
    return parse_decimal(val)
