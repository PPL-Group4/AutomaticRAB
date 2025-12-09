import sentry_sdk

def tag_excel_upload(file_obj):
    """Attach context about the uploaded Excel file."""
    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("component", "ExcelParser")
        scope.set_tag("file_name", file_obj.name)
        scope.set_tag("file_size_kb", round(file_obj.size / 1024, 2))
        scope.set_tag("content_type", file_obj.content_type)

def capture_parsing_error(file_obj, message):
    """Log parsing failures as Sentry events."""
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("component", "ExcelParser")
        scope.set_tag("event_type", "parsing_error")
        scope.set_extra("file_name", file_obj.name)
        scope.set_extra("file_size", file_obj.size)
        sentry_sdk.capture_message(message)
