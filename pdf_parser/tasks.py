"""
Celery tasks for PDF parsing.
"""
from celery import shared_task
from decimal import Decimal
import os

from .services.pipeline import parse_pdf_to_dtos
from cost_weight.models import TestJob, TestItem


@shared_task(bind=True, time_limit=900, soft_time_limit=870)
def process_pdf_file_task(self, file_path, filename):
    """
    Process a PDF file asynchronously.
    
    Args:
        file_path: Temporary file path to the uploaded PDF file
        filename: Original filename
    
    Returns:
        dict: Contains 'rows', 'job_id', 'filename'
    """
    try:
        # Update task state
        self.update_state(state='PROCESSING', meta={'status': 'Parsing PDF file...'})
        
        # Parse the PDF
        rows = parse_pdf_to_dtos(file_path)
        
        # Update task state
        self.update_state(state='PROCESSING', meta={'status': 'Creating test job...'})
        
        # Create TestJob from rows
        job = _create_test_job_from_rows(rows, filename)
        
        # Convert Decimals to floats for JSON serialization
        rows = _convert_decimals(rows)
        
        # Cleanup temp file
        if os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except OSError:
                pass
        
        return {
            'rows': rows,
            'job_id': job.id,
            'filename': filename,
            'status': 'completed'
        }
        
    except Exception as e:
        # Cleanup temp file on error
        if os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except OSError:
                pass
        
        # Re-raise the exception so Celery can handle it
        raise


def _convert_decimals(obj):
    """Recursively convert Decimal objects to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, list):
        return [_convert_decimals(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _convert_decimals(v) for k, v in obj.items()}
    return obj


def _create_test_job_from_rows(rows, filename="Uploaded PDF"):
    """
    Create TestJob and TestItems from parsed PDF rows.
    Returns the created TestJob instance.
    """
    # Create job
    job = TestJob.objects.create(name=f"RAB - {filename}")
    
    # Create items from rows (skip section headers)
    for row in rows:
        # Skip section/category rows
        if row.get("is_section") or row.get("job_match_status") == "skipped":
            continue
            
        description = row.get("description", "Unknown Item")
        if not description or description.strip() == "":
            continue
            
        # Parse quantity and price
        try:
            quantity = Decimal(str(row.get("volume", 0)))
            if quantity <= 0:
                quantity = Decimal("1")
        except (ValueError, TypeError, KeyError):
            quantity = Decimal("1")
            
        try:
            unit_price = Decimal(str(row.get("price", 0)))
            if unit_price < 0:
                unit_price = Decimal("0")
        except (ValueError, TypeError, KeyError):
            unit_price = Decimal("0")
        
        # Create item
        TestItem.objects.create(
            job=job,
            name=description,
            quantity=quantity,
            unit_price=unit_price
        )
    
    # Calculate totals and weights
    job.calculate_totals()
    
    return job
