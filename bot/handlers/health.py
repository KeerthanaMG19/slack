from django.http import JsonResponse
from django.conf import settings
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

def health_check(request):
    try:
        health_data = {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "django_debug": settings.DEBUG,
            "environment_variables": {
                "SLACK_BOT_TOKEN": bool(os.getenv('SLACK_BOT_TOKEN')),
                "SLACK_SIGNING_SECRET": bool(os.getenv('SLACK_SIGNING_SECRET')),
                "GEMINI_API_KEY": bool(os.getenv('GEMINI_API_KEY')),
                "DJANGO_SECRET_KEY": bool(os.getenv('DJANGO_SECRET_KEY'))
            }
        }
        logger.info(f"[{getattr(request, 'debug_id', 'unknown')}] Health check requested")
        return JsonResponse(health_data)
    except Exception as e:
        logger.error(f"[{getattr(request, 'debug_id', 'unknown')}] Health check failed: {str(e)}")
        return JsonResponse({
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }, status=500)
