import re
from typing import Any, Optional

from .interfaces import CellCleanerInterface


class CellCleaner(CellCleanerInterface):
    """
    Single Responsibility: Clean cell data
    """
    
    def clean_cell(self, value: Any) -> Optional[str]:
        """
        Clean cell value by removing unwanted characters and normalizing whitespace
        """
        if isinstance(value, str):
            # Replace non-breaking spaces and newlines first
            cleaned = value.replace('\u00A0', ' ').replace('\n', ' ').strip()
            # Collapse multiple spaces into one
            cleaned = re.sub(r'\s+', ' ', cleaned)
            return cleaned if cleaned else None
        return value
