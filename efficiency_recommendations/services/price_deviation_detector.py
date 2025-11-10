from typing import List, Dict, Optional
from decimal import Decimal
from enum import Enum


class DeviationLevel(str, Enum):
    """Severity levels for price deviations"""
    MODERATE = "MODERATE"   # 10-20% deviation
    HIGH = "HIGH"           # 20-50% deviation
    CRITICAL = "CRITICAL"   # >50% deviation


class PriceDeviationDetector:
    """
    Detects price deviations between actual and reference prices.
    
    Attributes:
        threshold_percentage: Minimum percentage deviation to trigger warning
                             Default is 10.0 (10%)
    """
    
    def __init__(self, threshold_percentage: float = 10.0):
        """
        Initialize the price deviation detector.
        
        Args:
            threshold_percentage: Minimum deviation % to trigger warning (default: 10%)
        """
        self.threshold_percentage = Decimal(str(threshold_percentage))
    
    def detect_deviations(self, items: List[Dict]) -> List[Dict]:
        """Detect price deviations for a list of items."""
        if not items:
            return []
        
        deviations = []
        
        for item in items:
            deviation = self._check_single_item(item)
            if deviation:
                deviations.append(deviation)
        
        # Sort by absolute deviation magnitude (highest first)
        deviations.sort(
            key=lambda x: abs(x['deviation_percentage']),
            reverse=True
        )
        
        return deviations
    
    def _check_single_item(self, item: Dict) -> Optional[Dict]:
        """Check a single item for price deviation."""
        actual_price = item.get('actual_price')
        reference_price = item.get('reference_price')
        item_name = item.get('name', 'Unknown Item')
        
        # Skip if missing data or zero reference price
        if actual_price is None or reference_price is None:
            return None
        if reference_price <= 0:
            return None
        
        # Calculate deviation percentage
        deviation_pct = self._calculate_deviation_percentage(
            actual_price, reference_price
        )
        
        # Check if deviation exceeds threshold
        if abs(deviation_pct) <= self.threshold_percentage:
            return None
        
        # Determine deviation level
        deviation_level = self._get_deviation_level(abs(deviation_pct))
        
        # Generate warning message
        message = self._generate_message(
            item_name, deviation_pct, actual_price, reference_price
        )
        
        return {
            'type': 'PRICE_DEVIATION',
            'item_name': item_name,
            'message': message,
            'deviation_percentage': deviation_pct,
            'deviation_level': deviation_level,
            'actual_price': actual_price,
            'reference_price': reference_price
        }
    
    def _calculate_deviation_percentage(
        self, actual: Decimal, reference: Decimal
    ) -> Decimal:
        """Calculate percentage deviation from reference price."""
        deviation = ((actual - reference) / reference) * 100
        # Round to 3 decimal places for precision
        return deviation.quantize(Decimal('0.001'))
    
    def _get_deviation_level(self, abs_deviation: Decimal) -> DeviationLevel:
        """Determine severity level based on absolute deviation percentage."""
        if abs_deviation > 50:
            return DeviationLevel.CRITICAL
        elif abs_deviation > 20:
            return DeviationLevel.HIGH
        else:
            return DeviationLevel.MODERATE
    
    def _generate_message(
        self,
        item_name: str,
        deviation_pct: Decimal,
        actual_price: Decimal,
        reference_price: Decimal
    ) -> str:
        """Generate formatted warning message for price deviation."""
        # Determine direction indicator
        direction = "higher" if deviation_pct > 0 else "lower"
        
        # Format prices with thousand separators
        actual_formatted = self._format_price(actual_price)
        reference_formatted = self._format_price(reference_price)
        
        # Build comprehensive message
        message = (
            f"Price deviation detected for '{item_name}': "
            f"{deviation_pct:+.1f}% {direction} than reference. "
            f"Actual: Rp {actual_formatted}, "
            f"Reference: Rp {reference_formatted}."
        )
        
        return message
    
    def _format_price(self, price: Decimal) -> str:
        """Format price with thousand separators."""
        return f"{price:,.0f}"


def detect_price_deviations(
    items: List[Dict],
    threshold_percentage: float = 10.0
) -> List[Dict]:
    """Convenience function to detect price deviations."""
    detector = PriceDeviationDetector(threshold_percentage)
    return detector.detect_deviations(items)
