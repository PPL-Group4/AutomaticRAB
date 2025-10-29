from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, List
from decimal import Decimal
from datetime import date

class CellCleanerInterface(ABC):
    """Interface for cleaning cell data"""
    
    @abstractmethod
    def clean_cell(self, value: Any) -> Optional[str]:
        """Clean a single cell value"""
        pass

class DataConverterInterface(ABC):
    """Interface for converting data types"""
    
    @abstractmethod
    def to_decimal(self, value: Any) -> Optional[Decimal]:
        """Convert value to Decimal"""
        pass
    
    @abstractmethod
    def to_percentage(self, value: Any) -> Optional[Decimal]:
        """Convert percentage string to decimal"""
        pass
    
    @abstractmethod
    def to_boolean(self, value: Any) -> Optional[bool]:
        """Convert string to boolean"""
        pass
    
    @abstractmethod
    def to_date(self, value: Any) -> Optional[date]:
        """Convert string to date"""
        pass

class RowClassifierInterface(ABC):
    """Interface for classifying row types"""
    
    @abstractmethod
    def classify_row(self, row_data: Dict[str, Any]) -> Optional[str]:
        """Classify the type of row"""
        pass

class RabParserInterface(ABC):
    """Main interface for RAB parsing operations"""
    
    @abstractmethod
    def parse_row(self, row_data: Dict[str, Any], project, parent=None):
        """Parse a single row into a RabEntry"""
        pass
