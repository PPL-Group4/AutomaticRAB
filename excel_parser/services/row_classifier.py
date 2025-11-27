from typing import Any, Dict, Optional

from ..models import RabEntry
from .interfaces import CellCleanerInterface, RowClassifierInterface


class RowClassifier(RowClassifierInterface):
    """
    Single Responsibility: Classify row types
    Dependency Inversion: Depends on CellCleanerInterface abstraction
    """
    
    def __init__(self, cell_cleaner: CellCleanerInterface):
        self.cell_cleaner = cell_cleaner

    def classify_row(self, row_data: Dict[str, Any]) -> Optional[str]:
        """Classify row type based on content and structure"""
        desc = self.cell_cleaner.clean_cell(row_data.get('URAIAN PEKERJAAN'))
        item_num = self.cell_cleaner.clean_cell(row_data.get('No.'))

        if not desc and not item_num:
            return None  # Skip empty rows

        if desc and desc.lower().startswith('terbilang'):
            return RabEntry.EntryType.GRAND_TOTAL
        if desc and desc.lower().startswith(('sub total', 'total')):
            return RabEntry.EntryType.SUB_TOTAL

        if item_num:
            # Roman numerals first
            if item_num.upper() in ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X']:
                return RabEntry.EntryType.SUB_SECTION
            # Single uppercase letter
            if item_num.isalpha() and len(item_num) == 1 and item_num.isupper():
                return RabEntry.EntryType.SECTION
            # Regular item with number
            return RabEntry.EntryType.ITEM
        
        # Site header (usually all caps)
        if desc and desc.isupper():
            return RabEntry.EntryType.SITE_HEADER

        # Default to item
        return RabEntry.EntryType.ITEM