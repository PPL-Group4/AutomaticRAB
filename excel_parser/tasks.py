"""
Celery tasks for Excel parsing.
"""
from celery import shared_task
from decimal import Decimal
from django.core.files.uploadedfile import InMemoryUploadedFile
from openpyxl import load_workbook
import tempfile
import os

from .services.reader import preview_file
from cost_weight.models import TestJob, TestItem


@shared_task(bind=True, time_limit=600, soft_time_limit=570)
def process_excel_file_task(self, file_path, filename, file_type='standard'):
    """
    Process an Excel file asynchronously.
    
    Args:
        file_path: Temporary file path to the uploaded Excel file
        filename: Original filename
        file_type: Type of file ('standard', 'apendo', or 'legacy')
    
    Returns:
        dict: Contains 'rows', 'job_id', 'filename', 'file_type'
    """
    try:
        # Update task state
        self.update_state(state='PROCESSING', meta={'status': 'Reading Excel file...'})
        
        # Process the file using existing preview_file logic
        # We need to create a file-like object from the path
        with open(file_path, 'rb') as f:
            rows = preview_file(f)
        
        # Update task state
        self.update_state(state='PROCESSING', meta={'status': 'Creating test job...'})
        
        # Create TestJob from rows
        job = _create_test_job_from_rows(rows, filename)
        
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
            'file_type': file_type,
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


def _create_test_job_from_rows(rows, filename="Uploaded File"):
    """
    Create TestJob and TestItems from parsed rows.
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
