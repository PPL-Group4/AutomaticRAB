import re
from decimal import Decimal, InvalidOperation
from datetime import date, datetime
from typing import Any, Optional
from .interfaces import DataConverterInterface

class DataConverter(DataConverterInterface):
    """
    Single Responsibility: Convert data types
    Open/Closed Principle: Easy to extend with new conversion methods
    """
    
    def to_decimal(self, value: Any) -> Optional[Decimal]:
        """
        Convert various numeric string formats to Decimal.
        Handles Indonesian, US, scientific notation formats.
        """
        if not value or not isinstance(value, str):
            return None
        
        try:
            # Remove currency symbols and whitespace
            cleaned_value = str(value).replace("Rp", "").strip()
            
            # Handle scientific notation first (contains 'E' or 'e')
            if 'E' in cleaned_value.upper():
                return Decimal(cleaned_value)
            
            # Check for US format with commas as thousands separators and period as decimal
            if ',' in cleaned_value and '.' in cleaned_value:
                parts = cleaned_value.split('.')
                if len(parts) == 2 and len(parts[1]) <= 3 and parts[1].isdigit():
                    # US format - remove commas, keep period
                    cleaned_value = cleaned_value.replace(",", "")
                else:
                    # Indonesian format - remove periods, replace comma with period
                    cleaned_value = cleaned_value.replace(".", "").replace(",", ".")
            elif ',' in cleaned_value:
                # Has comma but no period
                period_count = cleaned_value.count('.')
                if period_count >= 1:
                    # Indonesian format: "1.234,89"
                    cleaned_value = cleaned_value.replace(".", "").replace(",", ".")
                else:
                    # Just comma: "1234,56"
                    cleaned_value = cleaned_value.replace(",", ".")
            elif '.' in cleaned_value:
                # Only periods, no commas
                period_count = cleaned_value.count('.')
                if period_count > 1:
                    # Multiple periods: thousands separators
                    cleaned_value = cleaned_value.replace(".", "")
                elif period_count == 1:
                    # Single period - check if thousands or decimal
                    parts = cleaned_value.split('.')
                    if len(parts) == 2 and len(parts[1]) == 3 and parts[1] == '000':
                        # Thousands format like "5.000" -> "5000"
                        cleaned_value = parts[0] + parts[1]
            
            return Decimal(cleaned_value)
        except (InvalidOperation, ValueError):
            return None

    def to_percentage(self, value: Any) -> Optional[Decimal]:
        """Convert percentage string to decimal"""
        if not value or not isinstance(value, str):
            return None
        
        try:
            if value.strip().endswith('%'):
                numeric_part = value.strip()[:-1]
                percentage_value = Decimal(numeric_part)
                return percentage_value / 100
            return None
        except (InvalidOperation, ValueError):
            return None

    def to_boolean(self, value: Any) -> Optional[bool]:
        """Convert string to boolean"""
        if not value or not isinstance(value, str):
            return None
        
        cleaned = value.strip().lower()
        if cleaned == 'true':
            return True
        elif cleaned == 'false':
            return False
        return None

    def to_date(self, value: Any) -> Optional[date]:
        """Convert date string to date object"""
        if not value or not isinstance(value, str):
            return None
        
        cleaned = value.strip()
        
        try:
            # Try ISO format first: YYYY-MM-DD
            if '-' in cleaned:
                return datetime.strptime(cleaned, '%Y-%m-%d').date()
            # Try Indonesian format: DD/MM/YYYY
            elif '/' in cleaned:
                return datetime.strptime(cleaned, '%d/%m/%Y').date()
        except ValueError:
            pass
        
        return None