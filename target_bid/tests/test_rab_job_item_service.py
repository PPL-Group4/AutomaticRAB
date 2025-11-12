from decimal import Decimal
from types import SimpleNamespace
from django.test import SimpleTestCase
from target_bid.models.rab_job_item import RabJobItem
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

    def test_locked_items_classification(self):
        row_locked = SimpleNamespace(
            id=1, name="Locked", unit=None, rab_item_header=None,
            price=100, volume=1, custom_ahs_id=None, analysis_code=None, is_locked=True,
        )
        row_normal = SimpleNamespace(
            id=2, name="Normal", unit=None, rab_item_header=None,
            price=100, volume=2, custom_ahs_id=None, analysis_code=None, is_locked=False,
        )
        repo = SimpleNamespace(for_rab=lambda _: [row_locked, row_normal])
        service = RabJobItemService(repo, RabJobItemMapper())
        adjustable, locked, _ = service.get_items_with_classification(10)
        self.assertEqual(len(adjustable), 1)
        self.assertEqual(len(locked), 1)
