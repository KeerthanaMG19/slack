from django.http import JsonResponse
from django.conf import settings
from datetime import datetime
import os
import logging
import traceback

logger = logging.getLogger(__name__)

def slack_test_handler(request):
    try:
        request_id = getattr(request, 'debug_id', 'unknown')
        logger.info(f"[{request_id}] Test endpoint accessed")
        env_status = {}
        required_vars = ['SLACK_BOT_TOKEN', 'SLACK_SIGNING_SECRET', 'GEMINI_API_KEY', 'DJANGO_SECRET_KEY']
        for var in required_vars:
            value = os.getenv(var)
            if not value:
                env_status[var] = "❌ Missing"
            elif value.startswith('your-'):
                env_status[var] = "⚠️ Default template value"
            else:
                env_status[var] = "✅ Set"
        try:
            from ..services.slack_service import SlackService
            slack_service = SlackService()
            slack_status = "✅ Service initialized"
        except Exception as e:
            slack_status = f"❌ Error: {str(e)}"
        try:
            from ..services.gemini_service import GeminiService
            gemini_service = GeminiService()
            gemini_status = "✅ Service initialized"
        except Exception as e:
            gemini_status = f"❌ Error: {str(e)}"
        test_data = {
            "status": "Test endpoint working",
            "timestamp": datetime.now().isoformat(),
            "request_method": request.method,
            "host": request.get_host(),
            "is_ngrok": 'ngrok' in request.get_host(),
            "debug_mode": settings.DEBUG,
            "bot_name": "SlackOpsBot",
            "environment_variables": env_status,
            "services": {
                "slack_service": slack_status,
                "gemini_service": gemini_status
            },
            "endpoints": {
                "health": f"http://{request.get_host()}/health/",
                "slack_commands": f"http://{request.get_host()}/slack/commands/",
                "slack_events": f"http://{request.get_host()}/slack/events/"
            }
        }
        return JsonResponse(test_data, json_dumps_params={'indent': 2})
    except Exception as e:
        logger.error(f"[{getattr(request, 'debug_id', 'unknown')}] Test endpoint error: {str(e)}")
        return JsonResponse({
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "traceback": traceback.format_exc() if settings.DEBUG else None
        }, status=500)
