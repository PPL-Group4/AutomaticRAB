import logging
logger = logging.getLogger("excel_parser")
from django.core.exceptions import ValidationError

def validate_excel_file(file):
    valid_mimetypes = [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  
        "application/vnd.ms-excel", 
    ]
    if file.content_type not in valid_mimetypes:
        logger.warning("Rejected file=%s reason=invalid content_type=%s",
                       getattr(file, "name", "?"),
                       file.content_type)
        raise ValidationError("Only .xlsx and .xls files are allowed.")
    
    if not (file.name.endswith(".xls") or file.name.endswith(".xlsx")):
        logger.warning("Rejected file=%s reason=invalid extension", getattr(file, "name", "?"))
        raise ValidationError("File must have .xls or .xlsx extension")

    logger.info("File %s passed validation (content_type=%s)", file.name, file.content_type)