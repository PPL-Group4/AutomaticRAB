import pandas as pd
from decimal import Decimal, InvalidOperation
from typing import Optional, List, Dict, Any, Tuple
from django.core.files.uploadedfile import UploadedFile


def _find_column_matches(df_columns: List[str]) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Find matching columns for name, quantity, price, and total"""
    name_cols = ['item', 'description', 'pekerjaan', 'uraian', 'nama']
    qty_cols = ['quantity', 'qty', 'volume', 'kuantitas', 'jumlah']
    price_cols = ['unit price', 'unit_price', 'harga satuan', 'harga', 'price']
    total_cols = ['total', 'total price', 'total_price', 'jumlah harga']
    
    name_col = None
    qty_col = None
    price_col = None
    total_col = None
    
    for col in df_columns:
        if not name_col and any(nc in col for nc in name_cols):
            name_col = col
        if not qty_col and any(qc in col for qc in qty_cols):
            qty_col = col
        if not price_col and any(pc in col for pc in price_cols):
            price_col = col
        if not total_col and any(tc in col for tc in total_cols):
            total_col = col
    
    return name_col, qty_col, price_col, total_col


def _extract_item_name(row: pd.Series, name_col: Optional[str], idx: int) -> Optional[str]:
    """Extract item name from row"""
    if name_col and pd.notna(row.get(name_col)):
        item_name = str(row[name_col]).strip()
        if item_name and item_name != "" and item_name.lower() != "nan":
            return item_name
    return f"Item {idx + 1}"


def _extract_quantity(row: pd.Series, qty_col: Optional[str]) -> Decimal:
    """Extract quantity from row"""
    if qty_col and pd.notna(row.get(qty_col)):
        try:
            return Decimal(str(row[qty_col]))
        except (ValueError, InvalidOperation):
            return Decimal("1")
    return Decimal("1")


def _extract_unit_price(row: pd.Series, price_col: Optional[str]) -> Decimal:
    """Extract unit price from row"""
    if price_col and pd.notna(row.get(price_col)):
        try:
            return Decimal(str(row[price_col]))
        except (ValueError, InvalidOperation):
            return Decimal("0")
    return Decimal("0")


def _extract_total_cost(row: pd.Series, total_col: Optional[str], quantity: Decimal, unit_price: Decimal) -> Decimal:
    """Extract or calculate total cost from row"""
    if total_col and pd.notna(row.get(total_col)):
        try:
            return Decimal(str(row[total_col]))
        except (ValueError, InvalidOperation):
            return quantity * unit_price
    return quantity * unit_price


def _should_skip_row(item_name: Optional[str]) -> bool:
    """Check if row should be skipped"""
    return not item_name or item_name == "" or item_name.lower() == "nan"


def _parse_row(row: pd.Series, idx: int, name_col: Optional[str], qty_col: Optional[str], 
               price_col: Optional[str], total_col: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parse a single row and return item data"""
    item_name = _extract_item_name(row, name_col, idx)
    
    if _should_skip_row(item_name):
        return None
    
    quantity = _extract_quantity(row, qty_col)
    unit_price = _extract_unit_price(row, price_col)
    cost = _extract_total_cost(row, total_col, quantity, unit_price)
    
    return {
        'name': item_name,
        'quantity': quantity,
        'unit_price': unit_price,
        'cost': cost
    }


def _extract_job_name(file_obj: UploadedFile, job_name: Optional[str]) -> str:
    """Extract job name from file or provided name"""
    if job_name:
        return job_name
    
    extracted_name = getattr(file_obj, 'name', 'Unnamed Job')
    if extracted_name.endswith('.xlsx') or extracted_name.endswith('.xls'):
        return extracted_name.rsplit('.', 1)[0]
    
    return extracted_name


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
    
    name_col, qty_col, price_col, total_col = _find_column_matches(df.columns.tolist())
    
    items = []
    for idx, row in df.iterrows():
        try:
            item_data = _parse_row(row, idx, name_col, qty_col, price_col, total_col)
            if item_data:
                items.append(item_data)
        except Exception:
            continue
    
    total_cost = sum(item['cost'] for item in items)
    extracted_job_name = _extract_job_name(file_obj, job_name)
    
    return {
        'job_name': extracted_job_name,
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
