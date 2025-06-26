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
from .models import ChannelCategory

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
            # Add Channel to Category
            elif callback_id.startswith('add_channel_modal_'):
                try:
                    category_id = int(callback_id.split('_')[-1])
                    values = view.get('state', {}).get('values', {})
                    selected_channels = values.get('add_channel_select', {}).get('add_channel_select_input', {}).get('selected_channels', [])
                    # Fetch category name
                    categories = category_service.get_user_categories(user_id)
                    category = next((c for c in categories if c['id'] == category_id), None)
                    category_name = category['name'] if category else f"ID {category_id}"
                    for ch in selected_channels:
                        try:
                            channel_info = slack_service.get_channel_info(ch)
                            channel_name = channel_info.get('name', ch)
                        except Exception:
                            channel_name = ch
                        category_service.add_channel_to_category(category_id, ch, channel_name, user_id)
                    slack_service.send_message(
                        channel=user_id,
                        text=f":white_check_mark: Added {len(selected_channels)} channel(s) to *{category_name}*."
                    )
                    # Send updated category list
                    updated_categories = category_service.get_user_categories(user_id)
                    slack_service.send_message(
                        channel=user_id,
                        text=":information_source: Here is your updated category list.",
                        thread_ts=None,
                    )
                    slack_service.client.chat_postMessage(
                        channel=user_id,
                        blocks=block_kit_service.create_category_management_blocks(updated_categories)
                    )
                    return JsonResponse({'response_action': 'clear'})
                except Exception as e:
                    logger.error(f"[ADD_CHANNEL_MODAL] Error: {str(e)}", exc_info=True)
                    return JsonResponse({
                        'response_action': 'errors',
                        'errors': {
                            'category_name': f'Error: {str(e)}'
                        }
                    })
            # Remove Channel from Category
            elif callback_id.startswith('remove_channel_modal_'):
                try:
                    category_id = int(callback_id.split('_')[-1])
                    values = view.get('state', {}).get('values', {})
                    selected_channels = values.get('remove_channel_select', {}).get('remove_channel_select_input', {}).get('selected_options', [])
                    categories = category_service.get_user_categories(user_id)
                    category = next((c for c in categories if c['id'] == category_id), None)
                    category_name = category['name'] if category else f"ID {category_id}"
                    for ch in selected_channels:
                        channel_id = ch['value']
                        category_service.remove_channel_from_category(category_id, channel_id)
                    slack_service.send_message(
                        channel=user_id,
                        text=f":white_check_mark: Removed {len(selected_channels)} channel(s) from *{category_name}*."
                    )
                    updated_categories = category_service.get_user_categories(user_id)
                    slack_service.send_message(
                        channel=user_id,
                        text=":information_source: Here is your updated category list.",
                        thread_ts=None,
                    )
                    slack_service.client.chat_postMessage(
                        channel=user_id,
                        blocks=block_kit_service.create_category_management_blocks(updated_categories)
                    )
                    return JsonResponse({'response_action': 'clear'})
                except Exception as e:
                    logger.error(f"[REMOVE_CHANNEL_MODAL] Error: {str(e)}", exc_info=True)
                    return JsonResponse({
                        'response_action': 'errors',
                        'errors': {
                            'category_name': f'Error: {str(e)}'
                        }
                    })
            # Edit Category
            elif callback_id.startswith('edit_category_modal_'):
                try:
                    category_id = int(callback_id.split('_')[-1])
                    values = view.get('state', {}).get('values', {})
                    new_name = values.get('edit_category_name', {}).get('edit_category_name_input', {}).get('value', '')
                    new_desc = values.get('edit_category_description', {}).get('edit_category_description_input', {}).get('value', '')
                    old_categories = category_service.get_user_categories(user_id)
                    old_category = next((c for c in old_categories if c['id'] == category_id), None)
                    old_name = old_category['name'] if old_category else f"ID {category_id}"
                    category_service.rename_category(category_id, new_name, user_id)
                    # Optionally update description if supported
                    try:
                        cat = ChannelCategory.objects.get(id=category_id, created_by=user_id)
                        cat.description = new_desc
                        cat.save()
                    except Exception:
                        pass
                    slack_service.send_message(
                        channel=user_id,
                        text=f":white_check_mark: Category *{old_name}* updated to *{new_name}*."
                    )
                    updated_categories = category_service.get_user_categories(user_id)
                    slack_service.send_message(
                        channel=user_id,
                        text=":information_source: Here is your updated category list.",
                        thread_ts=None,
                    )
                    slack_service.client.chat_postMessage(
                        channel=user_id,
                        blocks=block_kit_service.create_category_management_blocks(updated_categories)
                    )
                    return JsonResponse({'response_action': 'clear'})
                except Exception as e:
                    logger.error(f"[EDIT_CATEGORY_MODAL] Error: {str(e)}", exc_info=True)
                    return JsonResponse({
                        'response_action': 'errors',
                        'errors': {
                            'category_name': f'Error: {str(e)}'
                        }
                    })
            # Delete Category
            elif callback_id.startswith('delete_category_modal_'):
                try:
                    category_id = int(callback_id.split('_')[-1])
                    # Fetch category name before deletion
                    categories = category_service.get_user_categories(user_id)
                    category = next((c for c in categories if c['id'] == category_id), None)
                    if not category:
                        slack_service.send_message(
                            channel=user_id,
                            text=f":warning: Category already deleted or does not exist."
                        )
                        return JsonResponse({'response_action': 'clear'})
                    category_name = category['name']
                    category_service.delete_category(category_id, user_id)
                    slack_service.send_message(
                        channel=user_id,
                        text=f":white_check_mark: Category *{category_name}* deleted."
                    )
                    updated_categories = category_service.get_user_categories(user_id)
                    slack_service.send_message(
                        channel=user_id,
                        text=":information_source: Here is your updated category list.",
                        thread_ts=None,
                    )
                    slack_service.client.chat_postMessage(
                        channel=user_id,
                        blocks=block_kit_service.create_category_management_blocks(updated_categories)
                    )
                    return JsonResponse({'response_action': 'clear'})
                except Exception as e:
                    logger.error(f"[DELETE_CATEGORY_MODAL] Error: {str(e)}", exc_info=True)
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
        if action_id == 'add_filter_condition':
            logger.info("[BLOCK_ACTION] Adding filter condition")
            # Open a modal for adding a condition
            modal_view = {
                "type": "modal",
                "callback_id": "add_filter_condition_modal",
                "title": {
                    "type": "plain_text",
                    "text": "Add Filter Condition",
                    "emoji": True
                },
                "submit": {
                    "type": "plain_text",
                    "text": "Add",
                    "emoji": True
                },
                "close": {
                    "type": "plain_text",
                    "text": "Cancel",
                    "emoji": True
                },
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "condition_text",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "condition_text_input",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Enter text to match"
                            }
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "Match Text",
                            "emoji": True
                        }
                    }
                ]
            }
            slack_service.client.views_open(
                trigger_id=trigger_id,
                view=modal_view
            )
            return JsonResponse({'ok': True})
            
        elif action_id == 'create_filter_submit':
            logger.info("[BLOCK_ACTION] Creating filter")
            # Get the filter name and match type from the blocks
            blocks = payload.get('state', {}).get('values', {})
            filter_name = blocks.get('filter_name', {}).get('filter_name_input', {}).get('value', '')
            match_type = blocks.get('match_type', {}).get('match_type_select', {}).get('selected_option', {}).get('value', 'all')
            
            if not filter_name:
                return JsonResponse({
                    'response_type': 'ephemeral',
                    'text': "Please enter a filter name"
                })
            
            try:
                # Create the filter
                filter = filter_service.create_filter(
                    name=filter_name,
                    match_type=match_type,
                    created_by=user_id
                )
                
                # Send success message
                return JsonResponse({
                    'response_type': 'ephemeral',
                    'text': f":white_check_mark: Filter *{filter_name}* created successfully!\nUse `/filter list` to see your filters."
                })
                
            except Exception as e:
                logger.error(f"[FILTER_CREATE] Error creating filter: {str(e)}", exc_info=True)
                return JsonResponse({
                    'response_type': 'ephemeral',
                    'text': f"Error creating filter: {str(e)}"
                })
        
        elif action_id == 'create_category':
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
        
        # Add Channel to Category
        elif action_id.startswith('add_channel_'):
            category_id = int(action_id.split('_')[-1])
            logger.info(f"[BLOCK_ACTION] Add Channel to Category {category_id}")
            # Open a modal to select channels to add
            modal_view = {
                "type": "modal",
                "callback_id": f"add_channel_modal_{category_id}",
                "title": {"type": "plain_text", "text": "Add Channel", "emoji": True},
                "submit": {"type": "plain_text", "text": "Add", "emoji": True},
                "close": {"type": "plain_text", "text": "Cancel", "emoji": True},
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "add_channel_select",
                        "element": {
                            "type": "multi_channels_select",
                            "action_id": "add_channel_select_input",
                            "placeholder": {"type": "plain_text", "text": "Select channels", "emoji": True}
                        },
                        "label": {"type": "plain_text", "text": "Channels to Add", "emoji": True}
                    }
                ]
            }
            slack_service.client.views_open(trigger_id=trigger_id, view=modal_view)
            return JsonResponse({'ok': True})

        # Remove Channel from Category
        elif action_id.startswith('remove_channel_'):
            category_id = int(action_id.split('_')[-1])
            logger.info(f"[BLOCK_ACTION] Remove Channel from Category {category_id}")
            # Open a modal to select channels to remove
            # FIX: Show channel names, not IDs
            category_channels = category_service.get_category_channels(category_id)
            # Fetch channel names for each channel_id
            channel_options = []
            for ch_id in category_channels:
                try:
                    channel_info = slack_service.get_channel_info(ch_id)
                    channel_name = channel_info.get('name', ch_id)
                except Exception:
                    channel_name = ch_id
                channel_options.append({
                    "text": {"type": "plain_text", "text": f"#{channel_name}", "emoji": True},
                    "value": ch_id
                })
            modal_view = {
                "type": "modal",
                "callback_id": f"remove_channel_modal_{category_id}",
                "title": {"type": "plain_text", "text": "Remove Channel", "emoji": True},
                "submit": {"type": "plain_text", "text": "Remove", "emoji": True},
                "close": {"type": "plain_text", "text": "Cancel", "emoji": True},
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "remove_channel_select",
                        "element": {
                            "type": "multi_static_select",
                            "action_id": "remove_channel_select_input",
                            "placeholder": {"type": "plain_text", "text": "Select channels", "emoji": True},
                            "options": channel_options
                        },
                        "label": {"type": "plain_text", "text": "Channels to Remove", "emoji": True}
                    }
                ]
            }
            slack_service.client.views_open(trigger_id=trigger_id, view=modal_view)
            return JsonResponse({'ok': True})

        # Edit Category (name/description)
        elif action_id.startswith('edit_category_'):
            category_id = int(action_id.split('_')[-1])
            logger.info(f"[BLOCK_ACTION] Edit Category {category_id}")
            # Fetch category details
            categories = category_service.get_user_categories(user_id)
            category = next((c for c in categories if c['id'] == category_id), None)
            modal_view = {
                "type": "modal",
                "callback_id": f"edit_category_modal_{category_id}",
                "title": {"type": "plain_text", "text": "Edit Category", "emoji": True},
                "submit": {"type": "plain_text", "text": "Save", "emoji": True},
                "close": {"type": "plain_text", "text": "Cancel", "emoji": True},
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "edit_category_name",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "edit_category_name_input",
                            "initial_value": category['name'] if category else "",
                            "placeholder": {"type": "plain_text", "text": "Enter category name"}
                        },
                        "label": {"type": "plain_text", "text": "Name", "emoji": True}
                    },
                    {
                        "type": "input",
                        "block_id": "edit_category_description",
                        "optional": True,
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "edit_category_description_input",
                            "multiline": True,
                            "initial_value": category['description'] if category else "",
                            "placeholder": {"type": "plain_text", "text": "Enter category description"}
                        },
                        "label": {"type": "plain_text", "text": "Description", "emoji": True}
                    }
                ]
            }
            slack_service.client.views_open(trigger_id=trigger_id, view=modal_view)
            return JsonResponse({'ok': True})

        # Delete Category
        elif action_id.startswith('delete_category_'):
            category_id = int(action_id.split('_')[-1])
            logger.info(f"[BLOCK_ACTION] Delete Category {category_id}")
            # Confirm deletion
            modal_view = {
                "type": "modal",
                "callback_id": f"delete_category_modal_{category_id}",
                "title": {"type": "plain_text", "text": "Delete Category", "emoji": True},
                "submit": {"type": "plain_text", "text": "Delete", "emoji": True},
                "close": {"type": "plain_text", "text": "Cancel", "emoji": True},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": ":warning: Are you sure you want to *delete* this category? This cannot be undone."
                        }
                    }
                ]
            }
            slack_service.client.views_open(trigger_id=trigger_id, view=modal_view)
            return JsonResponse({'ok': True})

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