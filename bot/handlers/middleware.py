import time
import logging
from django.middleware.csrf import CsrfViewMiddleware

logger = logging.getLogger(__name__)

class NgrokMiddleware:
    """Middleware to handle ngrok-specific headers and requests"""

    def __init__(self, get_response):
        self.get_response = get_response
        self.csrf_middleware = CsrfViewMiddleware(get_response)

    def __call__(self, request):
        # Log ALL incoming requests for debugging
        start_time = time.time()
        request_id = str(int(time.time() * 1000))[-6:]  # Last 6 digits for unique ID

        logger.info(f"[{request_id}] Incoming request: {request.method} {request.path}")
        logger.info(f"[{request_id}] Headers: {dict(request.headers)}")
        logger.info(f"[{request_id}] Host: {request.get_host()}")

        # Skip CSRF for Slack endpoints
        if '/slack/' in request.path:
            request._dont_enforce_csrf_checks = True
            logger.info(f"[{request_id}] Skipping CSRF check for Slack endpoint")

        # Log POST data for Slack commands
        if request.method == 'POST' and '/slack/' in request.path:
            logger.info(f"[{request_id}] POST data: {dict(request.POST)}")
            logger.info(f"[{request_id}] Body (first 500 chars): {request.body.decode('utf-8', errors='ignore')[:500]}")

        # Skip ngrok browser warning by adding the header
        if 'ngrok-skip-browser-warning' not in request.headers:
            request.META['HTTP_NGROK_SKIP_BROWSER_WARNING'] = 'true'

        # Add request ID to request for tracking
        request.debug_id = request_id

        response = self.get_response(request)

        # Log response details
        end_time = time.time()
        duration = (end_time - start_time) * 1000  # Convert to milliseconds
        logger.info(f"[{request_id}] Response: {response.status_code} in {duration:.2f}ms")

        # Add headers to skip ngrok warnings
        if self.is_ngrok_request(request):
            response['ngrok-skip-browser-warning'] = 'true'

        return response

    def is_ngrok_request(self, request):
        """Check if request is coming through ngrok"""
        host = request.get_host()
        user_agent = request.headers.get('User-Agent', '')

        return (
            '.ngrok.io' in host or 
            '.ngrok-free.app' in host or
            'ngrok' in user_agent.lower()
        )
