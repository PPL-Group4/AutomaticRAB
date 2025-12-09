from functools import lru_cache
from target_bid.services.cheaper_price_service import repo

@lru_cache(maxsize=5000)
def cached_cheaper_suggestions(name, unit, price):
    return tuple(repo.find_cheaper_same_unit(name, unit, price))
