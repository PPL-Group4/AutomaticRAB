"""
User Activity Monitoring Middleware
Tracks user actions and behaviors for analytics and issue detection
"""
import time
import sentry_sdk
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)


class UserActivityMiddleware(MiddlewareMixin):
    """
    Monitor USER ACTIVITY - what users are doing, not just feature performance.
    This is for analytics and detecting user-affecting issues.
    """
    
    def process_request(self, request):
        """Capture user context at start of request"""
        request._start_time = time.time()
        
        # Track user context in Sentry
        user_info = {
            "ip_address": self.get_client_ip(request),
            "user_agent": request.META.get('HTTP_USER_AGENT', 'Unknown'),
            "path": request.path,
            "method": request.method,
        }
        
        # If user is authenticated, add user info
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_info.update({
                "user_id": request.user.id,
                "username": request.user.username,
                "is_staff": request.user.is_staff,
            })
            sentry_sdk.set_user({
                "id": request.user.id,
                "username": request.user.username,
                "ip_address": user_info["ip_address"]
            })
        else:
            # Anonymous user
            sentry_sdk.set_user({
                "ip_address": user_info["ip_address"]
            })
        
        # Set request context for Sentry
        sentry_sdk.set_context("request_info", user_info)
        
        return None
    
    def process_response(self, request, response):
        """Track completed user actions"""
        if not hasattr(request, '_start_time'):
            return response
        
        duration = time.time() - request._start_time
        
        # Track specific user activities
        activity_type = self.classify_activity(request.path, request.method)
        
        if activity_type:
            # Log user activity to Sentry
            sentry_sdk.set_tag("event_type", "user_activity")
            sentry_sdk.set_tag("activity_type", activity_type)
            
            sentry_sdk.capture_message(
                f"User Activity: {activity_type}",
                level="info",
                extras={
                    "activity_type": activity_type,
                    "path": request.path,
                    "method": request.method,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                    "user_authenticated": hasattr(request, 'user') and request.user.is_authenticated,
                    "ip_address": self.get_client_ip(request),
                }
            )
            
            # Track failed user actions (these affect users!)
            if response.status_code >= 400:
                sentry_sdk.set_tag("event_type", "user_action_failed")
                sentry_sdk.capture_message(
                    f"User Action Failed: {activity_type}",
                    level="warning",
                    extras={
                        "activity_type": activity_type,
                        "path": request.path,
                        "status_code": response.status_code,
                        "error_type": self.get_error_type(response.status_code),
                    }
                )
        
        return response
    
    def classify_activity(self, path, method):
        """
        Classify what user action is happening
        This is USER ACTIVITY tracking, not feature profiling
        """
        if method == "GET":
            if "/admin/" in path:
                return "admin_page_view"
            elif any(x in path for x in ["/excel_parser/", "/pdf_parser/"]):
                return "file_upload_page_view"
            elif "/api/" in path:
                return "api_data_fetch"
            elif path == "/":
                return "homepage_view"
            else:
                return "page_view"
        
        elif method == "POST":
            if "/excel_parser/" in path:
                return "excel_file_upload"
            elif "/pdf_parser/" in path:
                return "pdf_file_upload"
            elif "/api/match" in path:
                return "job_matching_request"
            elif "/automatic_price_matching/" in path:
                return "price_matching_request"
            elif "/admin/" in path:
                return "admin_action"
            elif "/cost_weight/" in path:
                return "cost_weight_calculation"
            elif "/target_bid/" in path:
                return "target_bid_calculation"
            else:
                return "form_submission"
        
        elif method == "DELETE":
            return "data_deletion"
        
        elif method == "PUT" or method == "PATCH":
            return "data_update"
        
        return None
    
    def get_client_ip(self, request):
        """Get real client IP (handles proxies)"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def get_error_type(self, status_code):
        """Classify error type for users"""
        if status_code == 400:
            return "Invalid input from user"
        elif status_code == 401:
            return "Authentication required"
        elif status_code == 403:
            return "Access denied"
        elif status_code == 404:
            return "Resource not found"
        elif status_code == 413:
            return "File too large"
        elif status_code == 415:
            return "Unsupported file type"
        elif status_code == 429:
            return "Rate limit exceeded"
        elif status_code >= 500:
            return "Server error - user blocked"
        else:
            return f"HTTP {status_code}"
