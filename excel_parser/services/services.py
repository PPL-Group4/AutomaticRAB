import os

from django.core.exceptions import ValidationError
from openpyxl import load_workbook

try:
    import xlrd
except ImportError:
    xlrd = None

class ExcelSniffer:
    def is_valid(self, file_path):
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        try:
            if ext == ".xlsx":
                load_workbook(filename=file_path)
            elif ext == ".xls":
                if not xlrd:
                    raise ValidationError("Support for .xls requires xlrd==1.2.0")
                xlrd.open_workbook(file_path)
            else:
                raise ValidationError("Unsupported file extension. Only .xls or .xlsx allowed.")
        except Exception:
            raise ValidationError("Invalid Excel file or corrupted file.")
