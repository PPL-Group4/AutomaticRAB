import sentry_sdk

def tag_match_event(description: str, unit: str):
    """
    Add contextual info for Sentry events related to matching service.
    """
    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("component", "MatchingService")
        scope.set_tag("unit", unit or "unknown")
        scope.set_extra("description_length", len(description or ""))

def log_unmatched_entry(description: str, unit: str):
    """
    Send a custom event to Sentry for unmatched job descriptions.
    """
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("component", "MatchingService")
        scope.set_tag("match_status", "unmatched")
        scope.set_tag("unit", unit or "unknown")
        scope.set_extra("description_snippet", (description or "")[:100]) 
        sentry_sdk.capture_message("Unmatched job description")