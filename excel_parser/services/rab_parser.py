from datetime import date
from decimal import Decimal
from typing import Any, Dict, Optional

from ..models import RabEntry
from .interfaces import CellCleanerInterface, DataConverterInterface, RabParserInterface, RowClassifierInterface


class RabParser(RabParserInterface):
    """
    Main RAB Parser following SOLID principles:
    - Single Responsibility: Orchestrate parsing operations
    - Open/Closed: Easy to extend with new parsers
    - Liskov Substitution: Can substitute different implementations
    - Interface Segregation: Uses specific interfaces
    - Dependency Inversion: Depends on abstractions, not concretions
    """
    
    def __init__(
        self, 
        cell_cleaner: CellCleanerInterface,
        data_converter: DataConverterInterface,
        row_classifier: RowClassifierInterface
    ):
        self.cell_cleaner = cell_cleaner
        self.data_converter = data_converter
        self.row_classifier = row_classifier

    def parse_row(self, row_data: Dict[str, Any], project, parent=None) -> Optional[RabEntry]:
        """
        Parse a single row of RAB data into a RabEntry object.
        This method processes each cell after headers to clean and convert data types.
        """
        # Step 1: Classify the row type
        entry_type = self.row_classifier.classify_row(row_data)
        if entry_type is None:
            return None
        
        # Step 2: Clean and validate required fields
        desc = self.cell_cleaner.clean_cell(row_data.get('URAIAN PEKERJAAN'))
        if not desc:  # Skip rows without description
            return None
        
        # Step 3: Process each cell, cleaning and converting data types
        processed_data = self._process_all_cells(row_data)
        
        # Step 4: Create the RabEntry with processed data
        entry = RabEntry(
            project=project,
            parent=parent,
            entry_type=entry_type,
            item_number=processed_data['item_number'],
            description=processed_data['description'],
            unit=processed_data['unit'],
            analysis_code=processed_data['analysis_code'],
            volume=processed_data['volume'],
            unit_price=processed_data['unit_price'],
            total_price=processed_data['total_price']
        )
        
        # Step 5: Handle special cases (like grand total text)
        if entry_type == RabEntry.EntryType.GRAND_TOTAL and desc:
            parts = desc.split(':', 1)
            if len(parts) > 1:
                entry.total_price_in_words = parts[1].strip()
        
        return entry

    def _process_all_cells(self, row_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process all cells in the row, cleaning and converting data types.
        This ensures every cell is properly cleaned and typed for the internal DTO.
        """
        return {
            'item_number': self.cell_cleaner.clean_cell(row_data.get('No.')),
            'description': self.cell_cleaner.clean_cell(row_data.get('URAIAN PEKERJAAN')),
            'unit': self.cell_cleaner.clean_cell(row_data.get('SATUAN')),
            'analysis_code': self.cell_cleaner.clean_cell(row_data.get('KODE ANALISA')),
            'volume': self.data_converter.to_decimal(row_data.get('VOL.')),
            'unit_price': self.data_converter.to_decimal(row_data.get('HARGA SATUAN (Rp.)')),
            'total_price': self.data_converter.to_decimal(row_data.get('JUMLAH HARGA (Rp.)'))
        }

    # Expose individual methods for testing
    def clean_cell(self, value: Any) -> Optional[str]:
        """Delegate to cell cleaner"""
        return self.cell_cleaner.clean_cell(value)

    def to_decimal(self, value: Any) -> Optional['Decimal']:
        """Delegate to data converter"""
        return self.data_converter.to_decimal(value)

    def to_percentage(self, value: Any) -> Optional['Decimal']:
        """Delegate to data converter"""
        return self.data_converter.to_percentage(value)

    def to_boolean(self, value: Any) -> Optional[bool]:
        """Delegate to data converter"""
        return self.data_converter.to_boolean(value)

    def to_date(self, value: Any) -> Optional['date']:
        """Delegate to data converter"""
        return self.data_converter.to_date(value)

    def classify_row(self, row_data: Dict[str, Any]) -> Optional[str]:
        """Delegate to row classifier"""
        return self.row_classifier.classify_row(row_data)

