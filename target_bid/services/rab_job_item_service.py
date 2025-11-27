from collections.abc import Iterable, Sequence
from typing import List

from target_bid.models.rab_job_item import RabJobItem
from target_bid.repository.rab_item_repo import RabItemRepository
from target_bid.rules.decision_rules import (
    AnalysisCodeRule,
    CustomAhsOverrideRule,
    LockedItemRule,
    NameBlacklistRule,
)
from target_bid.utils.name_normaliser import NameNormaliser


class NonAdjustableEvaluator:
    def __init__(self, rules: Sequence):
        self._rules = list(rules)

    def classify(self, item: RabJobItem):
        for rule in self._rules:
            decision = rule.decide(item)
            if decision is not None:
                return decision, getattr(rule, "REASON_CODE", None)
        return False, None

class RabJobItemService:
    def __init__(self, repository: RabItemRepository, mapper, non_adjustable_policy=None):
        self._repository = repository
        self._mapper = mapper
        self._non_adjustable_policy = non_adjustable_policy or _DEFAULT_POLICY

    def get_items_with_classification(self, rab_id: int):
        mapped = self.map_rows(self._repository.for_rab(rab_id))
        return self.classify_mapped_items(mapped)

    def classify_mapped_items(self, mapped_items: Iterable[RabJobItem]):
        return _classify_items(list(mapped_items), self._non_adjustable_policy)

    def map_rows(self, rows: Iterable[object]) -> List[RabJobItem]:
        return [self._mapper.map(row) for row in rows]

def _classify_items(items, policy):
    adjustable, locked, excluded = [], [], []
    for item in items:
        decision, reason = policy.classify(item)
        if decision:
            if reason == LockedItemRule.REASON_CODE:
                locked.append(item)
            else:
                excluded.append((item, reason))
        else:
            adjustable.append(item)
    return adjustable, locked, excluded


_DEFAULT_NAME_NORMALISER = NameNormaliser()
_DEFAULT_NAME_RULE = NameBlacklistRule(
    {
        "rencana keselamatan konstruksi",
        "penyiapan dokumen penerapan smkk",
        "sosialisasi promosi dan pelatihan",
        "alat pelindung kerja apk",
        "alat pelindung kerja apk terdiri dari",
        "pembatas area",
        "alat pelindung diri apd",
        "alat pelindung diri apd terdiri dari",
        "helm pelindung",
        "sarung tangan",
        "kacamata pelindung",
        "sepatu keselamatan",
        "rompi keselamatan",
        "fasilitas sarana prasarana dan alat kesehatan",
        "peralatan p3k kotak p3k",
        "rambu dan perlengkapan lalu lintas",
        "alat pemadam api ringan apar",
    },
    _DEFAULT_NAME_NORMALISER,
)

_DEFAULT_RULES = [
    _DEFAULT_NAME_RULE,
    CustomAhsOverrideRule(),
    AnalysisCodeRule(),
    LockedItemRule(),
]

_DEFAULT_POLICY = NonAdjustableEvaluator(_DEFAULT_RULES)