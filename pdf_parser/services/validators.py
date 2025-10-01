from django.core.exceptions import ValidationError

def validate_pdf_file(file):
    """Allow only .pdf files with correct mimetype"""
    valid_mimetypes = ["application/pdf"]

    if not file.name.lower().endswith(".pdf"):
        raise ValidationError("Only .pdf files are allowed.")

    if file.content_type not in valid_mimetypes:
        raise ValidationError("Invalid file type. Only PDF files are supported.")
