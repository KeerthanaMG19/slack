from django.http import JsonResponse
import time
import logging
import threading
import requests
from django.conf import settings
from ..utils.channel_utils import parse_channel_name
from ..utils.summary_utils import (
    handle_summary_command,
    handle_summary_command_background,
    handle_unread_summary_command,
)
from ..utils.intent_recognition import IntentRecognizer
from .conversation_handler import ConversationHandler
from ..services.slack_service import SlackService
from ..services.gemini_service import GeminiService
from ..services.filter_service import FilterService
from ..services.category_service import CategoryService
from ..services.block_kit_service import BlockKitService
from ..models import User  # <-- Add this import

logger = logging.getLogger(__name__)

def slack_commands_handler(request):
    """Handle Slack slash commands with full AI-powered summaries"""
    request_id = getattr(request, 'debug_id', 'unknown')
    start_time = time.time()
    
    try:
        command = request.POST.get('command', '')
        text = request.POST.get('text', '').strip()
        user_id = request.POST.get('user_id', '')
        user_name = request.POST.get('user_name', '')
        channel_id = request.POST.get('channel_id', '')
        response_url = request.POST.get('response_url', '')
        
        # Initialize services
        slack_service = SlackService()
        gemini_service = GeminiService()
        filter_service = FilterService()
        category_service = CategoryService()
        block_kit_service = BlockKitService()
        
        # Parse command text
        txt_lower = text.lower()
        cmd = command.lower()

        # Show UI for creating/managing filters
        if cmd == '/filter':
            if txt_lower == 'create':
                return JsonResponse({
                    'response_type': 'ephemeral',
                    'blocks': block_kit_service.create_filter_creation_blocks()
                })
            elif txt_lower == 'list':
                filters = filter_service.get_user_filters(user_id)
                if not filters:
                    return JsonResponse({
                        'response_type': 'ephemeral',
                        'text': "You haven't created any filters yet. Use `/filter create` to create one!"
                    })
                return JsonResponse({
                    'response_type': 'ephemeral',
                    'blocks': block_kit_service.create_filter_select_block(filters, 'select_filter')
                })
            else:
                return JsonResponse({
                    'response_type': 'ephemeral',
                    'text': "Available filter commands:\n"
                           "• `/filter create` - Create a new filter\n"
                           "• `/filter list` - List your filters"
                })

        # Show UI for creating/managing categories
        if cmd == '/category':
            logger.info(f"[CATEGORY_COMMAND] Received command: {cmd} with text: {text}")
            
            if not text or txt_lower == 'list':
                logger.info("[CATEGORY_COMMAND] Listing categories")
                categories = category_service.get_user_categories(user_id)
                if not categories:
                    return JsonResponse({
                        'response_type': 'ephemeral',
                        'blocks': block_kit_service.create_category_management_blocks([])
                    })
                
                blocks = block_kit_service.create_category_management_blocks(categories)
                logger.info(f"[CATEGORY_COMMAND] Returning blocks for {len(categories)} categories")
                return JsonResponse({
                    'response_type': 'ephemeral',
                    'blocks': blocks
                })
            
            elif txt_lower == 'create':
                logger.info("[CATEGORY_COMMAND] Opening category creation modal")
                try:
                    trigger_id = request.POST.get('trigger_id')
                    if not trigger_id:
                        logger.error("[CATEGORY_COMMAND] No trigger_id found in request")
                        return JsonResponse({
                            'response_type': 'ephemeral',
                            'text': "Sorry, I couldn't open the category creation dialog. Please try again."
                        })
                    
                    # Create and open the modal
                    modal_view = block_kit_service.create_category_modal()
                    slack_service.client.views_open(
                        trigger_id=trigger_id,
                        view=modal_view
                    )
                    
                    return JsonResponse({
                        'response_type': 'ephemeral',
                        'text': "Opening category creation form..."
                    })
                    
                except Exception as e:
                    logger.error(f"[CATEGORY_COMMAND] Error opening modal: {str(e)}", exc_info=True)
                    return JsonResponse({
                        'response_type': 'ephemeral',
                        'text': f"Error: {str(e)}"
                    })
            
            else:
                logger.info("[CATEGORY_COMMAND] Showing help text")
                return JsonResponse({
                    'response_type': 'ephemeral',
                    'text': "Available category commands:\n"
                           "• `/category` - List your categories\n"
                           "• `/category create` - Create a new category"
                })

        # Add thread summary support FIRST
        if command == '/summary' and txt_lower.startswith('thread'):
            immediate_response = JsonResponse({
                'response_type': 'ephemeral',
                'blocks': block_kit_service.create_loading_message()['blocks']
            })
            def background_thread_summary():
                from ..utils.summary_utils import parse_summary_command
                thread_params = parse_summary_command(text)
                conversation_handler = ConversationHandler(slack_service, gemini_service)
                result = conversation_handler._handle_thread_command(thread_params, user_id)
                if response_url:
                    requests.post(response_url, json=result, timeout=10)
            threading.Thread(target=background_thread_summary, daemon=True).start()
            return immediate_response

        # /summary all
        if cmd in ['/summary', '/unread'] and txt_lower == 'all':
            immediate_response = JsonResponse({
                'response_type': 'ephemeral',
                'blocks': [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "📊 *Processing summaries for all channels...*\n\n"
                                  "🤖 AI analysis starting for each channel with new messages.\n"
                                  "📈 Generating comprehensive update across channels.\n"
                                  "⏱️ This may take 1-2 minutes for a complete analysis."
                        }
                    }
                ]
            })

            def background_all_process():
                try:
                    channels = slack_service.list_bot_channels()
                    if not channels:
                        if response_url:
                            error_payload = block_kit_service.create_error_message(
                                "No channels found or bot is not in any channels."
                            )
                            requests.post(response_url, json=error_payload, timeout=5)
                        return

                    summaries = []
                    for channel in channels:
                        try:
                            messages = slack_service.fetch_channel_messages(channel['id'])
                            if messages:
                                enriched_messages = slack_service.enrich_messages_with_usernames(messages)
                                summary = gemini_service.generate_summary(enriched_messages, channel['name'])
                                if summary:
                                    summaries.append(f"*#{channel['name']}*\n{summary.get('text', '')}\n")
                        except Exception as e:
                            logger.error(f"Error summarizing channel {channel['name']}: {str(e)}")
                            continue

                    if summaries:
                        combined_summary = {
                            'response_type': 'ephemeral',
                            'blocks': [
                                {
                                    "type": "section",
                                    "text": {
                                        "type": "mrkdwn",
                                        "text": "📊 *Summary of All Channels*\n\n" + "\n---\n".join(summaries)
                                    }
                                }
                            ]
                        }
                        if response_url:
                            requests.post(response_url, json=combined_summary, timeout=10)
                    else:
                        if response_url:
                            no_messages = block_kit_service.create_error_message(
                                "No new messages found in any channels since your last summary."
                            )
                            requests.post(response_url, json=no_messages, timeout=5)

                except Exception as e:
                    logger.error(f"Background all-channels processing error: {str(e)}")
                    if response_url:
                        error = block_kit_service.create_error_message(
                            f"Error generating summaries: {str(e)[:100]}..."
                        )
                        requests.post(response_url, json=error, timeout=5)

            background_thread = threading.Thread(target=background_all_process)
            background_thread.daemon = True
            background_thread.start()
            return immediate_response

        # /summary category [category-name]
        if cmd == '/summary' and txt_lower.startswith('category'):
            category_name = text[9:].strip()  # Remove "category " prefix
            if not category_name:
                categories = category_service.get_user_categories(user_id)
                return JsonResponse({
                    'response_type': 'ephemeral',
                    'blocks': block_kit_service.create_category_select_block(categories, 'select_category')
                })

            immediate_response = JsonResponse({
                'response_type': 'ephemeral',
                'blocks': block_kit_service.create_loading_message()['blocks']
            })

            def background_category_process():
                try:
                    categories = category_service.get_user_categories(user_id)
                    category = next((c for c in categories if c['name'].lower() == category_name.lower()), None)
                    
                    if not category:
                        if response_url:
                            error = block_kit_service.create_error_message(
                                f"Category '{category_name}' not found."
                            )
                            requests.post(response_url, json=error, timeout=5)
                        return

                    summaries = []
                    for channel in category['channels']:
                        try:
                            messages = slack_service.fetch_channel_messages(channel['id'])
                            if messages:
                                enriched_messages = slack_service.enrich_messages_with_usernames(messages)
                                summary = gemini_service.generate_summary(enriched_messages, channel['name'])
                                summary_text = summary.get('text', '') if summary else f"📭 No summary generated for #{channel['name']}."
                            else:
                                # Fallback summary for no messages
                                summary_text = (
                                    f"📊 **Summary Report for #{channel['name']}**\n\n"
                                    f"📋 Channel Status:\n"
                                    f"🔹 No messages found in the last 24 hours\n"
                                    f"🔹 Channel appears inactive\n\n"
                                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                    f"📈 Report Details: No recent activity\n"
                                    f"🤖 AI Analysis: Generated on {time.strftime('%Y-%m-%d %H:%M')}\n"
                                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                                )
                            summaries.append(f"*#{channel['name']}*\n{summary_text}\n")
                        except Exception as e:
                            logger.error(f"Error summarizing channel {channel['name']}: {str(e)}")
                            # Still append a block for this channel with error info
                            summaries.append(
                                f"*#{channel['name']}*\n"
                                f":x: Error generating summary for this channel.\n"
                                f"Error: {str(e)[:100]}\n"
                            )

                    if summaries:
                        combined_summary = {
                            'response_type': 'ephemeral',
                            'blocks': [
                                {
                                    "type": "section",
                                    "text": {
                                        "type": "mrkdwn",
                                        "text": f"📊 *Summary of {category_name} Category*\n\n" + "\n---\n".join(summaries)
                                    }
                                }
                            ]
                        }
                        if response_url:
                            requests.post(response_url, json=combined_summary, timeout=10)
                    else:
                        if response_url:
                            no_messages = block_kit_service.create_error_message(
                                f"No new messages found in {category_name} category channels."
                            )
                            requests.post(response_url, json=no_messages, timeout=5)

                except Exception as e:
                    logger.error(f"Background category processing error: {str(e)}")
                    if response_url:
                        error = block_kit_service.create_error_message(
                            f"Error generating category summary: {str(e)[:100]}..."
                        )
                        requests.post(response_url, json=error, timeout=5)

            background_thread = threading.Thread(target=background_category_process)
            background_thread.daemon = True
            background_thread.start()
            return immediate_response

        # Regular channel summary with optional filter
        if cmd == '/summary':
            # Show UI for summary options if no channel specified
            if not text:
                return JsonResponse({
                    'response_type': 'ephemeral',
                    'blocks': block_kit_service.create_summary_options_block()
                })

            # Parse filter if specified
            filter_id = None
            if ' filter:' in txt_lower:
                parts = text.split(' filter:', 1)
                text = parts[0]
                filter_name = parts[1].strip()
                filters = filter_service.get_user_filters(user_id)
                matching_filter = next((f for f in filters if f.name.lower() == filter_name.lower()), None)
                if matching_filter:
                    filter_id = matching_filter.id
                else:
                    return JsonResponse({
                        'response_type': 'ephemeral',
                        'text': f"Filter '{filter_name}' not found. Use `/filter list` to see available filters."
                    })

            channel_name = parse_channel_name(text) or 'current channel'
            immediate_response = JsonResponse({
                'response_type': 'ephemeral',
                'blocks': block_kit_service.create_loading_message()['blocks']
            })

            def background_summary():
                try:
                    messages = slack_service.fetch_channel_messages(channel_id)
                    if messages and filter_id:
                        messages = filter_service.apply_filter(messages, filter_id)
                    
                    if messages:
                        enriched_messages = slack_service.enrich_messages_with_usernames(messages)
                        summary = gemini_service.generate_summary(enriched_messages, channel_name)
                        if summary:
                            result = {
                                'response_type': 'in_channel',
                                'blocks': [
                                    {
                                        "type": "section",
                                        "text": {
                                            "type": "mrkdwn",
                                            "text": summary.get('text', '')
                                        }
                                    }
                                ],
                                'replace_original': True
                            }
                            if response_url:
                                requests.post(response_url, json=result, timeout=10)
                        else:
                            error = block_kit_service.create_error_message(
                                "Failed to generate summary. Please try again."
                            )
                            if response_url:
                                requests.post(response_url, json=error, timeout=5)
                    else:
                        no_messages = block_kit_service.create_error_message(
                            "No messages found matching your criteria."
                        )
                        if response_url:
                            requests.post(response_url, json=no_messages, timeout=5)

                except Exception as e:
                    logger.error(f"Background summary processing error: {str(e)}")
                    if response_url:
                        error = block_kit_service.create_error_message(
                            f"Error generating summary: {str(e)[:100]}..."
                        )
                        requests.post(response_url, json=error, timeout=5)

            background_thread = threading.Thread(target=background_summary)
            background_thread.daemon = True
            background_thread.start()
            return immediate_response

        # /summary vip
        if cmd == '/summary' and txt_lower == 'vip':
            immediate_response = JsonResponse({
                'response_type': 'ephemeral',
                'blocks': [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "🌟 *Processing summaries for all VIP user DMs...*\n\n"
                                    "🤖 AI analysis starting for each VIP user's direct messages.\n"
                                    "⏱️ This may take a few seconds."
                        }
                    }
                ]
            })

            def background_vip_dm_process():
                try:
                    # Dynamically fetch all users from Slack
                    slack_users = slack_service.client.users_list()['members']
                    # Define your VIP criteria here (example: custom profile field 'vip' == True)
                    vip_users = [
                        u for u in slack_users
                        if not u.get('deleted', False)
                        and not u.get('is_bot', False)
                        and u.get('profile', {}).get('fields', {})
                        and any(
                            f.get('value', '').lower() == 'true'
                            for f in u['profile']['fields'].values()
                            if isinstance(f, dict)
                        )
                    ]
                    summaries = []
                    for vip in vip_users:
                        vip_id = vip['id']
                        vip_name = vip['profile'].get('real_name', vip.get('name', vip_id))
                        dm_channel_id = slack_service.get_dm_channel_id(vip_id)
                        if not dm_channel_id:
                            summaries.append(f"*{vip_name}*: :x: Could not open DM channel.")
                            continue
                        messages = slack_service.fetch_unread_dm_messages(dm_channel_id, vip_id)
                        if messages:
                            enriched = slack_service.enrich_messages_with_usernames(messages)
                            summary = gemini_service.summarize_messages(enriched, f"DM with {vip_name}")
                            summaries.append(f"*{vip_name}*\n{summary}\n")
                        else:
                            summaries.append(f"*{vip_name}*: 📭 No new unread messages.")
                    if summaries:
                        combined = {
                            'response_type': 'ephemeral',
                            'blocks': [
                                {
                                    "type": "section",
                                    "text": {
                                        "type": "mrkdwn",
                                        "text": "🌟 *VIP DM Summaries*\n\n" + "\n---\n".join(summaries)
                                    }
                                }
                            ]
                        }
                        if response_url:
                            requests.post(response_url, json=combined, timeout=10)
                except Exception as e:
                    logger.error(f"VIP DM summary error: {str(e)}")
                    if response_url:
                        error = block_kit_service.create_error_message(
                            f"Error generating VIP DM summaries: {str(e)[:100]}..."
                        )
                        requests.post(response_url, json=error, timeout=5)

            threading.Thread(target=background_vip_dm_process, daemon=True).start()
            return immediate_response

        logger.warning(f"Unknown command received: {command}")
        return JsonResponse({
            'response_type': 'ephemeral',
            'blocks': [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Available Commands:*\n\n"
                               "• `/summary #channel-name` - Get channel summary\n"
                               "• `/summary #channel-name filter:filter-name` - Get filtered summary\n"
                               "• `/summary category category-name` - Get category summary\n"
                               "• `/summary all` - Get summary of all channels\n"
                               "• `/category create` - Create a channel category\n"
                               "• `/category list` - List your categories\n"
                               "• `/filter create` - Create a message filter\n"
                               "• `/filter list` - List your filters"
                    }
                }
            ]
        })

    except Exception as e:
        elapsed = (time.time() - start_time) * 1000
        logger.error(f"Command error after {elapsed:.1f}ms: {str(e)}")
        return JsonResponse(block_kit_service.create_error_message(
            "An unexpected error occurred. Please try again."
        ))

def slack_commands_fast_handler(request):
    """Fast slash command handler that works with limited permissions"""
    request_id = getattr(request, 'debug_id', 'unknown')
    
    try:
        command = request.POST.get('command', '')
        text = request.POST.get('text', '')
        user_name = request.POST.get('user_name', '')
        channel_id = request.POST.get('channel_id', '')
        
        logger.info(f"[{request_id}] 🚀 Fast command: {command} in {channel_id}")
        
        if command == '/summary':
            channel_name = parse_channel_name(text) or 'current channel'
            
            # Return immediate helpful response without trying to access restricted APIs
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': f'🤖 **Beta-Summarizer Bot Status**\n\n' +
                       f'✅ **Bot is working!** Command received from @{user_name}\n' +
                       f'📝 **Requested:** Summary for #{channel_name}\n\n' +
                       f'⚠️ **Current Issue:** Missing OAuth permissions\n' +
                       f'🔧 **Quick Fix:** Add these scopes to your Slack app:\n\n' +
                       f'**Required OAuth Scopes:**\n' +
                       f'• `channels:read` - List and view channels\n' +
                       f'• `channels:history` - Read channel messages  \n' +
                       f'• `users:read` - Get user names\n' +
                       f'• `chat:write` - Send responses\n\n' +
                       f'**How to fix:**\n' +
                       f'1. Go to https://api.slack.com/apps\n' +
                       f'2. Select your app → OAuth & Permissions\n' +
                       f'3. Add the scopes above\n' +
                       f'4. Reinstall the app to your workspace\n\n' +
                       f'✨ **Once fixed, I\'ll provide full AI-powered summaries!**'
            })
        
        return JsonResponse({
            'response_type': 'ephemeral',
            'text': f'❓ Unknown command: {command}'
        })
        
    except Exception as e:
        logger.error(f"[{request_id}] Fast command error: {str(e)}")
        return JsonResponse({
            'response_type': 'ephemeral',
            'text': '✅ Bot is running, but needs proper OAuth permissions to function fully.'
        })

def slack_commands_ultra_fast_handler(request):
    """Ultra-fast slash command handler that responds instantly and processes asynchronously"""
    request_id = getattr(request, 'debug_id', 'unknown')
    start_time = time.time()
    
    try:
        command = request.POST.get('command', '')
        text = request.POST.get('text', '').strip()
        user_name = request.POST.get('user_name', '')
        user_id = request.POST.get('user_id', '')
        channel_id = request.POST.get('channel_id', '')
        response_url = request.POST.get('response_url', '')
        
        logger.info(f"[{request_id}] ⚡ Ultra-fast command: {command} with text: '{text}'")
        
        # Check command type
        is_unread_request = (
            text.lower().startswith('unread ') or
            'unread' in text.lower() or 
            command == '/unread'
        )
        
        is_all_request = (
            text.lower() == 'all' or
            text.lower().startswith('all ')
        )
        
        # Add thread summary support FIRST
        if command == '/summary' and text.lower().startswith('thread'):
            immediate_response = JsonResponse({
                'response_type': 'ephemeral',
                'text': ':zap: Processing thread summary...\nThis will take just a moment!'
            })
            def background_thread_summary():
                from ..utils.summary_utils import parse_summary_command
                thread_params = parse_summary_command(text)
                conversation_handler = ConversationHandler(SlackService(), GeminiService())
                result = conversation_handler._handle_thread_command(thread_params, user_id)
                if response_url:
                    requests.post(response_url, json=result, timeout=10)
            threading.Thread(target=background_thread_summary, daemon=True).start()
            return immediate_response

        if command == '/summary' or command == '/unread':
            # Handle /summary all command
            if is_all_request:
                logger.info(f"[{request_id}] 📊 Processing summary for all channels")
                
                def background_all_process():
                    try:
                        logger.info(f"[{request_id}] 🔄 Starting background analysis for all channels")
                        
                        # Import services here to avoid circular imports
                        from ..services.slack_service import SlackService
                        from ..services.gemini_service import GeminiService
                        from ..models import UserSummaryState
                        
                        # Initialize services
                        slack_service = SlackService()
                        gemini_service = GeminiService()
                        
                        # Get all channels the bot is in
                        channels = slack_service.list_bot_channels()
                        
                        if not channels:
                            if response_url:
                                error_payload = {
                                    'response_type': 'ephemeral',
                                    'text': "❌ No channels found or bot is not in any channels.",
                                    'replace_original': True
                                }
                                requests.post(response_url, json=error_payload, timeout=5)
                            return
                        
                        # Get last summary timestamps for all channels
                        summaries = []
                        
                        for channel in channels:
                            channel_id = channel['id']
                            channel_name = channel['name']
                            
                            try:
                                # Get messages since last summary
                                last_ts = UserSummaryState.get_last_summary_ts(user_id, channel_id)
                                messages = slack_service.fetch_channel_messages(channel_id, oldest_ts=last_ts)
                                
                                if messages:
                                    enriched_messages = slack_service.enrich_messages_with_usernames(messages)
                                    if enriched_messages:
                                        summary = gemini_service.generate_summary(enriched_messages, channel_name)
                                        if summary:
                                            summaries.append(f"*#{channel_name}*\n{summary.get('text', '')}\n")
                                            # Update last summary timestamp
                                            newest_ts = max(msg['ts'] for msg in messages)
                                            UserSummaryState.update_last_summary_ts(user_id, channel_id, newest_ts)
                            except Exception as e:
                                logger.error(f"Error summarizing channel {channel_name}: {str(e)}")
                                continue
                        
                        if summaries:
                            combined_summary = "📊 *Summary of All Channels*\n\n" + "\n---\n".join(summaries)
                            
                            if response_url:
                                followup_payload = {
                                    'response_type': 'ephemeral',
                                    'text': combined_summary,
                                    'replace_original': True
                                }
                                requests.post(response_url, json=followup_payload, timeout=10)
                        else:
                            if response_url:
                                error_payload = {
                                    'response_type': 'ephemeral',
                                    'text': "📭 No new messages found in any channels since your last summary.",
                                    'replace_original': True
                                }
                                requests.post(response_url, json=error_payload, timeout=5)
                                
                    except Exception as e:
                        logger.error(f"[{request_id}] ❌ Background all-channels processing error: {str(e)}")
                        if response_url:
                            error_payload = {
                                'response_type': 'ephemeral',
                                'text': f"❌ Error generating summaries.\n\nError: {str(e)[:100]}...",
                                'replace_original': True
                            }
                            try:
                                requests.post(response_url, json=error_payload, timeout=5)
                            except:
                                pass
                
                # Start background thread
                background_thread = threading.Thread(target=background_all_process)
                background_thread.daemon = True
                background_thread.start()
                
                # IMMEDIATE response for all channels
                response = JsonResponse({
                    'response_type': 'ephemeral',
                    'text': f'📊 **Processing summaries for all channels...**\n\n' +
                           f'🤖 AI analysis starting for each channel with new messages.\n' +
                           f'📈 Generating comprehensive update across channels.\n' +
                           f'⏱️ This may take 1-2 minutes for a complete analysis.\n\n' +
                           f'✨ **Your multi-channel summary will appear shortly!**'
                })
                
            # Handle /summary unread [channel] command
            elif is_unread_request:
                logger.info(f"[{request_id}] 📬 Processing unread request")
                
                # Parse the actual channel name (remove "unread " prefix if present)
                if text.lower().startswith('unread '):
                    actual_text = text[6:].strip()
                else:
                    actual_text = text
                
                channel_name = parse_channel_name(actual_text) or 'specified channel'
                
                def background_unread_process():
                    try:
                        logger.info(f"[{request_id}] 🔄 Starting background unread analysis for #{channel_name}")
                        unread_response = handle_unread_summary_command(actual_text, user_name, user_id, f"{request_id}-unread")
                        
                        if hasattr(unread_response, 'content'):
                            import json
                            unread_data = json.loads(unread_response.content.decode('utf-8'))
                            unread_text = unread_data.get('text', 'Unread summary completed.')
                            
                            if response_url:
                                followup_payload = {
                                    'response_type': 'ephemeral',
                                    'text': unread_text,
                                    'replace_original': True
                                }
                                try:
                                    followup_response = requests.post(response_url, json=followup_payload, timeout=10)
                                    if followup_response.status_code == 200:
                                        logger.info(f"[{request_id}] ✅ Unread summary posted successfully")
                                    else:
                                        logger.error(f"[{request_id}] ❌ Failed to post unread summary: {followup_response.status_code}")
                                except Exception as e:
                                    logger.error(f"[{request_id}] ❌ Error posting unread summary: {str(e)}")
                        
                    except Exception as e:
                        logger.error(f"[{request_id}] ❌ Background unread processing error: {str(e)}")
                        if response_url:
                            error_payload = {
                                'response_type': 'ephemeral',
                                'text': f'❌ Sorry, there was an error generating your unread summary for #{channel_name}.\n\n' +
                                       f'Please try again in a few moments.\n' +
                                       f'Error: {str(e)[:100]}...',
                                'replace_original': True
                            }
                            try:
                                requests.post(response_url, json=error_payload, timeout=5)
                            except:
                                pass
                
                # Start background thread
                background_thread = threading.Thread(target=background_unread_process)
                background_thread.daemon = True
                background_thread.start()
                
                # IMMEDIATE response for unread
                response = JsonResponse({
                    'response_type': 'ephemeral',
                    'text': f'📬 **Checking unread messages for #{channel_name}...**\n\n' +
                           f'🔍 AI analyzing messages you haven\'t seen yet.\n' +
                           f'⚡ Personalized catch-up summary generating now.\n' +
                           f'⏱️ This usually takes 5-15 seconds.\n\n' +
                           f'📋 **Your personalized unread summary will appear shortly!**'
                })
                
            # Handle regular /summary [channel] command
            else:
                logger.info(f"[{request_id}] 📊 Processing regular summary request")
                channel_name = parse_channel_name(text) or 'specified channel'
                
                def background_process():
                    try:
                        logger.info(f"[{request_id}] 🔄 Starting background AI summary for #{channel_name}")
                        summary_response = handle_summary_command_background(text, user_name, f"{request_id}-bg")
                        
                        if hasattr(summary_response, 'content'):
                            import json
                            summary_data = json.loads(summary_response.content.decode('utf-8'))
                            summary_text = summary_data.get('text', 'Summary generation completed.')
                            
                            if response_url:
                                followup_payload = {
                                    'response_type': 'in_channel',
                                    'text': summary_text,
                                    'replace_original': True
                                }
                                try:
                                    followup_response = requests.post(response_url, json=followup_payload, timeout=10)
                                    if followup_response.status_code == 200:
                                        logger.info(f"[{request_id}] ✅ AI summary posted successfully")
                                    else:
                                        logger.error(f"[{request_id}] ❌ Failed to post summary: {followup_response.status_code}")
                                except Exception as e:
                                    logger.error(f"[{request_id}] ❌ Error posting summary: {str(e)}")
                        
                    except Exception as e:
                        logger.error(f"[{request_id}] ❌ Background processing error: {str(e)}")
                        if response_url:
                            error_payload = {
                                'response_type': 'ephemeral',
                                'text': f'❌ Sorry, there was an error generating the summary for #{channel_name}.\n\n' +
                                       f'Please try again in a few moments.\n' +
                                       f'Error: {str(e)[:100]}...',
                                'replace_original': True
                            }
                            try:
                                requests.post(response_url, json=error_payload, timeout=5)
                            except:
                                pass
                
                # Start background thread
                background_thread = threading.Thread(target=background_process)
                background_thread.daemon = True
                background_thread.start()
                
                # IMMEDIATE response
                response = JsonResponse({
                    'response_type': 'ephemeral',
                    'text': f'⚡ **Processing summary for #{channel_name}...**\n\n' +
                           f'🤖 AI analysis starting now with full OAuth permissions.\n' +
                           f'📊 Fetching messages and generating intelligent summary.\n' +
                           f'⏱️ This usually takes 10-30 seconds for detailed analysis.\n\n' +
                           f'✨ **Full AI-powered summary will appear shortly!**'
                })
            
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"[{request_id}] ⚡ Ultra-fast response sent in {elapsed:.1f}ms, background processing started")
            
            return response
        
        logger.warning(f"[{request_id}] ❓ Unknown command received: {command}")
        return JsonResponse({
            'response_type': 'ephemeral',
            'text': f'❌ Unknown command: {command}\n\n' +
                   f'Available commands:\n' +
                   f'• `/summary #channel-name` - Get channel summary\n' +
                   f'• `/summary unread #channel-name` - Get unread messages summary\n' +
                   f'• `/summary all` - Get summary of all channels'
        })
        
    except Exception as e:
        elapsed = (time.time() - start_time) * 1000
        logger.error(f"[{request_id}] Ultra-fast command error after {elapsed:.1f}ms: {str(e)}")
        return JsonResponse({
            'response_type': 'ephemeral',
            'text': '❌ Error processing your request. Please try again.'
        })