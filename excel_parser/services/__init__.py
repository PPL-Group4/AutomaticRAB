from .cell_cleaner import CellCleaner
from .data_converter import DataConverter
from .row_classifier import RowClassifier
from .rab_parser import RabParser

# Factory function following Dependency Injection pattern
def create_rab_parser() -> RabParser:
    """Factory function to create a fully configured RabParser"""
    cell_cleaner = CellCleaner()
    data_converter = DataConverter()
    row_classifier = RowClassifier(cell_cleaner)
    
    return RabParser(cell_cleaner, data_converter, row_classifier)