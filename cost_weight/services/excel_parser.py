"""
Excel Parser untuk RAB - Parse Excel dan create job items dengan cost weight
"""
from decimal import Decimal
from typing import Any, Dict, Optional

import pandas as pd
from django.core.files.uploadedfile import UploadedFile


def parse_rab_excel(file_obj: UploadedFile, job_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse RAB Excel file and extract items with quantities and prices
    
    Returns dict with:
    - job_name: str
    - items: List[Dict] with keys: name, quantity, unit_price, cost
    - total_cost: Decimal
    """
    # Read Excel file
    df = pd.read_excel(file_obj)
    
    # Clean column names
    df.columns = df.columns.str.strip().str.lower()
    
    items = []
    
    # Try to find relevant columns (flexible matching)
    name_cols = ['item', 'description', 'pekerjaan', 'uraian', 'nama']
    qty_cols = ['quantity', 'qty', 'volume', 'kuantitas', 'jumlah']
    price_cols = ['unit price', 'unit_price', 'harga satuan', 'harga', 'price']
    total_cols = ['total', 'total price', 'total_price', 'jumlah harga']
    
    name_col = None
    qty_col = None
    price_col = None
    total_col = None
    
    # Find matching columns
    for col in df.columns:
        if not name_col and any(nc in col for nc in name_cols):
            name_col = col
        if not qty_col and any(qc in col for qc in qty_cols):
            qty_col = col
        if not price_col and any(pc in col for pc in price_cols):
            price_col = col
        if not total_col and any(tc in col for tc in total_cols):
            total_col = col
    
    # Parse each row
    for idx, row in df.iterrows():
        try:
            # Get item name
            if name_col and pd.notna(row.get(name_col)):
                item_name = str(row[name_col]).strip()
            else:
                item_name = f"Item {idx + 1}"
            
            # Skip empty rows
            if not item_name or item_name == "" or item_name.lower() == "nan":
                continue
            
            # Get quantity
            if qty_col and pd.notna(row.get(qty_col)):
                try:
                    quantity = Decimal(str(row[qty_col]))
                except:
                    quantity = Decimal("1")
            else:
                quantity = Decimal("1")
            
            # Get unit price
            if price_col and pd.notna(row.get(price_col)):
                try:
                    unit_price = Decimal(str(row[price_col]))
                except:
                    unit_price = Decimal("0")
            else:
                unit_price = Decimal("0")
            
            # Calculate or get total cost
            if total_col and pd.notna(row.get(total_col)):
                try:
                    cost = Decimal(str(row[total_col]))
                except:
                    cost = quantity * unit_price
            else:
                cost = quantity * unit_price
            
            items.append({
                'name': item_name,
                'quantity': quantity,
                'unit_price': unit_price,
                'cost': cost
            })
            
        except Exception:
            # Skip problematic rows
            continue
    
    # Calculate total
    total_cost = sum(item['cost'] for item in items)
    
    # Get job name
    if not job_name:
        job_name = getattr(file_obj, 'name', 'Unnamed Job')
        if job_name.endswith('.xlsx') or job_name.endswith('.xls'):
            job_name = job_name.rsplit('.', 1)[0]
    
    return {
        'job_name': job_name,
        'items': items,
        'total_cost': total_cost
    }


def create_job_from_excel(file_obj: UploadedFile, job_name: Optional[str] = None):
    """
    Parse Excel and create TestJob with TestItems
    """
    from cost_weight.models import TestItem, TestJob
    
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
