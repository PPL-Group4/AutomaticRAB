from decimal import Decimal

from django.test import TestCase

from target_bid.models.rab_job_item import RabJobItem
from target_bid.rules.decision_rules import AnalysisCodeRule, CustomAhsOverrideRule, LockedItemRule


class LockedItemRuleTests(TestCase):
    def test_locked_item_returns_true(self):
        item = RabJobItem(1, "Work", "m", Decimal("1"), Decimal("1"), Decimal("1"), None, None, None, None, True)
        self.assertTrue(LockedItemRule().decide(item))

    def test_unlocked_item_returns_none(self):
        item = RabJobItem(2, "Work", "m", None, None, None, None, None, None, None, False)
        self.assertIsNone(LockedItemRule().decide(item))


class OtherRulesTests(TestCase):
    def test_custom_ahs_override_returns_false(self):
        item = RabJobItem(1, "Work", "m", None, None, None, None, None, 123, None)
        self.assertFalse(CustomAhsOverrideRule().decide(item))

    def test_analysis_code_returns_true(self):
        item = RabJobItem(1, "Work", "m", None, None, None, None, None, None, "AT.01")
        self.assertTrue(AnalysisCodeRule().decide(item))
