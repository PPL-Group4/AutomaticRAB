from target_bid.models.rab_job_item import RabJobItem, DecimalAdapter

class RabJobItemMapper:
    def __init__(self, decimal_adapter: type[DecimalAdapter] = DecimalAdapter):
        self._decimal = decimal_adapter

    def map(self, row):
        unit = getattr(row, "unit", None)
        header = getattr(row, "rab_item_header", None)
        raw_code = getattr(row, "analysis_code", None)
        analysis_code = (raw_code or "").strip() or None

        unit_price = self._decimal.to_decimal(getattr(row, "price", None))
        volume = self._decimal.to_decimal(getattr(row, "volume", None))
        total_price = self._decimal.multiply(volume, unit_price)

        return RabJobItem(
            rab_item_id=getattr(row, "id"),
            name=(getattr(row, "name", "") or ""),
            unit_name=getattr(unit, "name", None),
            unit_price=unit_price,
            volume=volume,
            total_price=total_price,
            rab_item_header_id=getattr(header, "id", None),
            rab_item_header_name=getattr(header, "name", None),
            custom_ahs_id=getattr(row, "custom_ahs_id", None),
            analysis_code=analysis_code,
            is_locked=getattr(row, "is_locked", False),
        )
