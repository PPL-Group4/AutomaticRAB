from collections.abc import Sequence
from typing import Optional

from target_bid.models.rab_job_item import RabJobItem


class LockedItemRule:
    REASON_CODE = "locked"
    def decide(self, item: RabJobItem) -> Optional[bool]:
        if getattr(item, "is_locked", None) is True:
            return True
        return None

class CustomAhsOverrideRule:
    REASON_CODE = "custom_ahs_override"
    def decide(self, item: RabJobItem) -> Optional[bool]:
        if item.custom_ahs_id is not None:
            return False
        return None

class AnalysisCodeRule:
    REASON_CODE = "analysis_code"
    def decide(self, item: RabJobItem) -> Optional[bool]:
        return bool(item.analysis_code)

class NameBlacklistRule:
    REASON_CODE = "name_blacklist"
    def __init__(self, blacklist: Sequence[str], normaliser):
        self._blacklist = set(blacklist)
        self._normaliser = normaliser

    def decide(self, item: RabJobItem) -> Optional[bool]:
        normalised = self._normaliser.normalise(item.name)
        if normalised in self._blacklist:
            return True
        return None
