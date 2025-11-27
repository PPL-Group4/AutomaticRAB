from collections.abc import Iterable
from typing import Protocol

from rencanakan_core.models import RabItem


class RabItemRepository(Protocol):
    def for_rab(self, rab_id: int) -> Iterable[object]:
        ...

class DjangoRabItemRepository:
    def for_rab(self, rab_id: int) -> Iterable[object]:
        return (
            RabItem.objects.select_related("unit", "rab_item_header")
            .filter(rab_id=rab_id)
            .order_by("id")
        )
