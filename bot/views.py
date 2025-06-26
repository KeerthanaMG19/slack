from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from django.conf import settings
import logging
import os
from datetime import datetime
from asgiref.sync import async_to_sync
import json
import threading

from .handlers.middleware import NgrokMiddleware
from .handlers.health import health_check
from .handlers.slack_test import slack_test_handler
from .handlers.slack_events import slack_events_handler
from .handlers.slack_commands import (
    slack_commands_handler,
    slack_commands_fast_handler,
    slack_commands_ultra_fast_handler,
)
from .utils.channel_utils import parse_channel_name
from .services.slack_service import SlackService
from .services.gemini_service import GeminiService
from .services.category_service import CategoryService
from .services.filter_service import FilterService
from .services.block_kit_service import BlockKitService

logger = logging.getLogger(__name__)

@xframe_options_exempt
def index(request):
    """Basic view that returns 'Slack bot is running'"""
    # Log request details for debugging
    logger.info(f"[{getattr(request, 'debug_id', 'unknown')}] Index request from: {request.get_host()}")
    
    # Handle ngrok browser warning page
    if 'ngrok-skip-browser-warning' in request.headers:
        logger.info(f"[{getattr(request, 'debug_id', 'unknown')}] Skipping ngrok browser warning")
    
    return HttpResponse("Slack bot is running")

@csrf_exempt
def health(request):
    """Health check endpoint"""
    return health_check(request)

@csrf_exempt
def slack_test(request):
    """Test endpoint for configuration verification"""
    return slack_test_handler(request)

@csrf_exempt
def slack_events(request):
    """Handle Slack events"""
    if request.method == 'POST':
        return slack_events_handler(request)
    return HttpResponse("Method not allowed", status=405)

@csrf_exempt
@require_POST
def slack_commands(request):
    """Endpoint for Slack slash commands"""
    try:
        command = request.POST.get('command')
        # Route all commands to the main handler
        from .handlers.slack_commands import slack_commands_handler
        return slack_commands_handler(request)
    except Exception as e:
        logger.error(f"Error handling slash command: {str(e)}", exc_info=True)
        return JsonResponse({
            'response_type': 'ephemeral',
            'text': ':x: Sorry, something went wrong processing your command.'
        })

@csrf_exempt
@require_http_methods(["POST"])
def slack_commands_fast(request):
    """Fast slash command handler that works with limited permissions"""
    return slack_commands_fast_handler(request)

@csrf_exempt
@require_http_methods(["POST"])
def slack_commands_ultra_fast(request):
    """Ultra-fast slash command handler that responds instantly and processes asynchronously"""
    return slack_commands_ultra_fast_handler(request)

def handle_summary_command(text, user_id, channel_id):
    """
    Handles /summary and /unread commands with flexible argument parsing.
    """
    args = text.strip().split()
    command = args[0] if args else ""
    params = args[1:] if len(args) > 1 else []

    # Thread summary support
    if command in ["/summary", "/unread"]:
        params = args[1:] if len(args) > 1 else []

        # Handle /summary thread [latest] [channel]
        if params and params[0] == "thread":
            # e.g. /summary thread latest social
            thread_params = params[1:]
            if thread_params and thread_params[0] == "latest" and len(thread_params) > 1:
                # thread latest <channel>
                return summarize_thread_latest(thread_params[1])
            elif thread_params:
                # thread <something else>
                return summarize_thread(thread_params)
            else:
                # thread only, use current thread context if possible
                return summarize_thread_in_context(channel_id)
        # Handle /summary all
        if params and params[0] == "all":
            summary_type = "all"
            target_channel = None
        # Handle /summary unread [#channel-name]
        elif params and params[0] == "unread":
            summary_type = "unread"
            if len(params) > 1:
                target_channel = params[1].lstrip("#")
        # Handle /summary [#channel-name]
        elif params:
            target_channel = params[0].lstrip("#")
        # Handle /unread [#channel-name]
        elif command == "/unread":
            summary_type = "unread"
            if params:
                target_channel = params[0].lstrip("#")
        # /summary or /unread with no params: use current channel

        # Call the appropriate summary function
        if summary_type == "all":
            return summarize_all_channels(user_id)
        elif summary_type == "unread":
            return summarize_unread(target_channel, user_id)
        else:
            return summarize_channel(target_channel, user_id)
    else:
        return "Unknown command."

def send_summary_to_slack(channel_id, user_id, command_text):
    # Your existing summary logic here
    summary = handle_summary_command(command_text, user_id, channel_id)
    # Use your SlackService or Slack client to send the summary back
    SlackService().post_message(channel_id, summary)

def slack_command_view(request):
    # ...existing code to parse request...
    command_text = request.POST.get('text', '')
    channel_id = request.POST.get('channel_id')
    user_id = request.POST.get('user_id')
    # Immediately acknowledge to Slack to avoid timeout
    ack_message = {"response_type": "ephemeral", "text": "Working on your summary..."}
    response = JsonResponse(ack_message)
    # Start background thread for summarization
    threading.Thread(
        target=send_summary_to_slack,
        args=(channel_id, user_id, command_text),
        daemon=True
    ).start()
    return response

# Example usage in your Slack event handler:
# response = handle_summary_command(command_text, user_id, channel_id)

@csrf_exempt
@require_POST
def handle_block_actions(request):
    """Handle interactive Block Kit actions and view submissions"""
    try:
        # Parse the payload
        payload = json.loads(request.POST.get('payload', '{}'))
        logger.info(f"[INTERACTION] Received payload type: {payload.get('type')}")
        
        # Initialize services
        category_service = CategoryService()
        filter_service = FilterService()
        block_kit_service = BlockKitService()
        slack_service = SlackService()
        
        # Get user info
        user_id = payload.get('user', {}).get('id')
        logger.info(f"[INTERACTION] User ID: {user_id}")
        
        # Handle view submissions
        if payload.get('type') == 'view_submission':
            view = payload.get('view', {})
            callback_id = view.get('callback_id')
            logger.info(f"[VIEW_SUBMISSION] Callback ID: {callback_id}")
            
            if callback_id == 'create_category_modal':
                try:
                    # Get values from the modal
                    values = view.get('state', {}).get('values', {})
                    logger.info(f"[CATEGORY_CREATE] Modal values: {values}")
                    
                    # Extract values with detailed logging
                    name = values.get('category_name', {}).get('category_name_input', {}).get('value', '')
                    logger.info(f"[CATEGORY_CREATE] Name: {name}")
                    
                    description = values.get('category_description', {}).get('category_description_input', {}).get('value', '')
                    logger.info(f"[CATEGORY_CREATE] Description: {description}")
                    
                    selected_channels = values.get('category_channels', {}).get('category_channels_input', {}).get('selected_channels', [])
                    logger.info(f"[CATEGORY_CREATE] Selected channels: {selected_channels}")
                    
                    if not name:
                        logger.warning("[CATEGORY_CREATE] No name provided")
                        return JsonResponse({
                            'response_action': 'errors',
                            'errors': {
                                'category_name': 'Please enter a category name'
                            }
                        })
                    
                    # Create the category
                    logger.info(f"[CATEGORY_CREATE] Creating category with name={name}, description={description}, channels={selected_channels}")
                    category = category_service.create_category(
                        name=name,
                        description=description,
                        channels=selected_channels,
                        created_by=user_id
                    )
                    logger.info(f"[CATEGORY_CREATE] Category created successfully with ID: {category.id}")
                    
                    # Send a success message
                    slack_service.send_message(
                        channel=user_id,
                        text=f":white_check_mark: Category *{name}* created successfully with {len(selected_channels)} channels!"
                    )
                    
                    # Return success response
                    logger.info("[CATEGORY_CREATE] Returning success response")
                    return JsonResponse({
                        'response_action': 'clear'
                    })
                    
                except Exception as e:
                    logger.error(f"[CATEGORY_CREATE] Error creating category: {str(e)}", exc_info=True)
                    return JsonResponse({
                        'response_action': 'errors',
                        'errors': {
                            'category_name': f'Error: {str(e)}'
                        }
                    })
            
            logger.warning(f"[VIEW_SUBMISSION] Unknown callback_id: {callback_id}")
            return JsonResponse({
                'response_action': 'errors',
                'errors': {
                    'category_name': 'Unknown submission type'
                }
            })
        
        # Handle block actions
        trigger_id = payload.get('trigger_id')
        action = payload.get('actions', [{}])[0]
        action_id = action.get('action_id', '')
        logger.info(f"[BLOCK_ACTION] Action ID: {action_id}")
        
        # Handle different actions
        if action_id == 'create_category':
            logger.info("[BLOCK_ACTION] Opening category creation modal")
            # Open a modal for category creation
            modal_view = block_kit_service.create_category_modal()
            response = slack_service.client.views_open(
                trigger_id=trigger_id,
                view=modal_view
            )
            logger.info(f"[BLOCK_ACTION] Modal opened successfully: {response}")
            return JsonResponse({'ok': True})
            
        elif action_id.startswith('manage_category_'):
            category_id = int(action_id.split('_')[-1])
            logger.info(f"[BLOCK_ACTION] Managing category {category_id}")
            return JsonResponse({
                'response_type': 'ephemeral',
                'blocks': [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Category Management*"
                        }
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Add Channel",
                                    "emoji": True
                                },
                                "value": str(category_id),
                                "action_id": f"add_channel_{category_id}"
                            },
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Remove Channel",
                                    "emoji": True
                                },
                                "value": str(category_id),
                                "action_id": f"remove_channel_{category_id}"
                            },
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Delete Category",
                                    "emoji": True
                                },
                                "style": "danger",
                                "value": str(category_id),
                                "action_id": f"delete_category_{category_id}"
                            }
                        ]
                    }
                ]
            })
        
        logger.warning(f"[BLOCK_ACTION] Unsupported action: {action_id}")
        return JsonResponse({
            'response_type': 'ephemeral',
            'text': 'Action not supported'
        })

    except Exception as e:
        logger.error(f"[INTERACTION] Unhandled error: {str(e)}", exc_info=True)
        return JsonResponse({
            'response_action': 'errors',
            'errors': {
                'category_name': f'Error: {str(e)}'
            }
        })