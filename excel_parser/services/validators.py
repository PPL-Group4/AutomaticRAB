from django.core.exceptions import ValidationError

def validate_excel_file(file):
    valid_mimetypes = [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  
        "application/vnd.ms-excel", 
    ]
    if file.content_type not in valid_mimetypes:
        raise ValidationError("Only .xlsx and .xls files are allowed.")
