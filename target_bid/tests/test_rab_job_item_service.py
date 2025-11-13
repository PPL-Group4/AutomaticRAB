from unittest.mock import MagicMock
from types import SimpleNamespace
from django.test import SimpleTestCase
from target_bid.services.rab_job_item_service import RabJobItemService
from target_bid.utils.rab_job_item_mapper import RabJobItemMapper
from target_bid.rules.decision_rules import LockedItemRule  

class RabJobItemServiceTests(SimpleTestCase):
    def test_service_maps_rows(self):
        row = SimpleNamespace(id=1, name="Work", price=100, volume=2, unit=None, rab_item_header=None)
        repo = SimpleNamespace(for_rab=lambda _: [row])
        service = RabJobItemService(repo, RabJobItemMapper())
        items = service.get_items_with_classification(1)
        self.assertTrue(len(items[0]) > 0)

    def test_get_items_with_classification_groups_correctly(self):
        """Ensure RabJobItemService groups items into adjustable, locked, excluded."""
        repo = SimpleNamespace(for_rab=lambda _: ["dummy_row1", "dummy_row2"])
        mapper = MagicMock()
        mapper.map.side_effect = ["item1", "item2"]

        fake_policy = MagicMock()
        fake_policy.classify.side_effect = [
            (True, LockedItemRule.REASON_CODE),  
            (False, None),
        ]

        service = RabJobItemService(repo, mapper, non_adjustable_policy=fake_policy)
        adjustable, locked, excluded = service.get_items_with_classification(42)

        self.assertEqual(adjustable, ["item2"])
        self.assertEqual(locked, ["item1"])
        self.assertEqual(excluded, [])
        self.assertEqual(fake_policy.classify.call_count, 2)
