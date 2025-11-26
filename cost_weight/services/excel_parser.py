"""
Excel Parser untuk RAB - Parse Excel dan create job items dengan cost weight
"""
import pandas as pd
from decimal import Decimal, InvalidOperation
from typing import Optional, List, Dict, Any
from django.core.files.uploadedfile import UploadedFile


def _find_column_match(df_columns: List[str], possible_names: List[str]) -> Optional[str]:
    """Find first matching column from list of possible names."""
    for col in df_columns:
        if any(name in col for name in possible_names):
            return col
    return None


def _safe_decimal_conversion(value: Any, default: Decimal) -> Decimal:
    """Safely convert value to Decimal, return default on error."""
    try:
        return Decimal(str(value))
    except (ValueError, InvalidOperation, TypeError):
        return default


def _get_column_mappings(df_columns: List[str]) -> Dict[str, Optional[str]]:
    """Find all relevant column mappings."""
    name_cols = ['item', 'description', 'pekerjaan', 'uraian', 'nama']
    qty_cols = ['quantity', 'qty', 'volume', 'kuantitas', 'jumlah']
    price_cols = ['unit price', 'unit_price', 'harga satuan', 'harga', 'price']
    total_cols = ['total', 'total price', 'total_price', 'jumlah harga']
    
    return {
        'name': _find_column_match(df_columns, name_cols),
        'quantity': _find_column_match(df_columns, qty_cols),
        'price': _find_column_match(df_columns, price_cols),
        'total': _find_column_match(df_columns, total_cols)
    }


def _extract_item_name(row: pd.Series, name_col: Optional[str], idx: int) -> Optional[str]:
    """Extract and validate item name from row."""
    if name_col and pd.notna(row.get(name_col)):
        item_name = str(row[name_col]).strip()
    else:
        item_name = f"Item {idx + 1}"
    
    if not item_name or item_name == "" or item_name.lower() == "nan":
        return None
    return item_name


def _extract_quantity(row: pd.Series, qty_col: Optional[str]) -> Decimal:
    """Extract quantity from row."""
    if qty_col and pd.notna(row.get(qty_col)):
        return _safe_decimal_conversion(row[qty_col], Decimal("1"))
    return Decimal("1")


def _extract_unit_price(row: pd.Series, price_col: Optional[str]) -> Decimal:
    """Extract unit price from row."""
    if price_col and pd.notna(row.get(price_col)):
        return _safe_decimal_conversion(row[price_col], Decimal("0"))
    return Decimal("0")


def _calculate_cost(row: pd.Series, quantity: Decimal, unit_price: Decimal, total_col: Optional[str]) -> Decimal:
    """Calculate or extract total cost."""
    cost = quantity * unit_price
    if total_col and pd.notna(row.get(total_col)):
        return _safe_decimal_conversion(row[total_col], cost)
    return cost


def _parse_row_to_item(row: pd.Series, idx: int, columns: Dict[str, Optional[str]]) -> Optional[Dict[str, Any]]:
    """Parse a single row into an item dictionary."""
    item_name = _extract_item_name(row, columns['name'], idx)
    if not item_name:
        return None
    
    quantity = _extract_quantity(row, columns['quantity'])
    unit_price = _extract_unit_price(row, columns['price'])
    cost = _calculate_cost(row, quantity, unit_price, columns['total'])
    
    return {
        'name': item_name,
        'quantity': quantity,
        'unit_price': unit_price,
        'cost': cost
    }


def _normalize_job_name(file_obj: UploadedFile, job_name: Optional[str]) -> str:
    """Get or normalize job name from file."""
    if job_name:
        return job_name
    
    job_name = getattr(file_obj, 'name', 'Unnamed Job')
    if job_name.endswith('.xlsx') or job_name.endswith('.xls'):
        job_name = job_name.rsplit('.', 1)[0]
    return job_name


def parse_rab_excel(file_obj: UploadedFile, job_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse RAB Excel file and extract items with quantities and prices
    
    Returns dict with:
    - job_name: str
    - items: List[Dict] with keys: name, quantity, unit_price, cost
    - total_cost: Decimal
    """
    df = pd.read_excel(file_obj)
    df.columns = df.columns.str.strip().str.lower()
    
    columns = _get_column_mappings(df.columns)
    items = []
    
    for idx, row in df.iterrows():
        try:
            item = _parse_row_to_item(row, idx, columns)
            if item:
                items.append(item)
        except Exception:
            continue
    
    total_cost = sum(item['cost'] for item in items)
    
    return {
        'job_name': _normalize_job_name(file_obj, job_name),
        'items': items,
        'total_cost': total_cost
    }


def create_job_from_excel(file_obj: UploadedFile, job_name: Optional[str] = None):
    """
    Parse Excel and create TestJob with TestItems
    """
    from cost_weight.models import TestJob, TestItem
    
    # Parse Excel
    parsed = parse_rab_excel(file_obj, job_name)
    
    # Create Job
    job = TestJob.objects.create(
        name=parsed['job_name'],
        excel_file=file_obj
    )
    
    # Create Items
    for item_data in parsed['items']:
        TestItem.objects.create(
            job=job,
            name=item_data['name'],
            quantity=item_data['quantity'],
            unit_price=item_data['unit_price']
            # cost will be auto-calculated by model save()
        )
    
    # Calculate totals and weights
    job.calculate_totals()
    
    return job
