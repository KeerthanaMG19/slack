from django.http import JsonResponse
import time
import logging
import re
from ..services.slack_service import SlackService
from ..services.gemini_service import GeminiService

logger = logging.getLogger(__name__)

def handle_summary_command(text, user_name, request_id):
    """Handle the /summary command workflow with comprehensive error handling"""
    # Track overall start time for timeout protection
    start_time = time.time()
    step_start = time.time()
    
    try:
        logger.info(f"[{request_id}] 🔍 Step 1: Parsing channel name")
        
        # Parse channel name from command text
        channel_name = parse_channel_name(text)
        logger.info(f"[{request_id}] Parsed channel name: '{channel_name}'")
        
        if not channel_name:
            logger.info(f"[{request_id}] ❌ No channel name provided")
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': '📝 Please specify a channel to summarize.\n\n' +
                       'Usage: `/summary #channel-name`\n' +
                       'Examples:\n' +
                       '• `/summary #general`\n' +
                       '• `/summary general`\n' +
                       '• `/summary #random`'
            })
        
        step_duration = (time.time() - step_start) * 1000
        logger.info(f"[{request_id}] ✅ Step 1 completed in {step_duration:.2f}ms")
        
        # Step 2: Initialize services
        step_start = time.time()
        logger.info(f"[{request_id}] 🔧 Step 2: Initializing services")
        
        try:
            slack_service = SlackService()
            gemini_service = GeminiService()
            step_duration = (time.time() - step_start) * 1000
            logger.info(f"[{request_id}] ✅ Step 2 completed in {step_duration:.2f}ms")
        except Exception as e:
            logger.error(f"[{request_id}] ❌ Step 2 failed: Service initialization error: {str(e)}", exc_info=True)
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': f"❌ Service initialization failed. Please contact administrator.\nError: {str(e)[:100]}"
            })
        
        # Step 3: Find channel ID
        step_start = time.time()
        logger.info(f"[{request_id}] 🔍 Step 3: Looking up channel ID for: {channel_name}")
        
        try:
            channel_id = slack_service.find_channel_id(channel_name)
            step_duration = (time.time() - step_start) * 1000
            logger.info(f"[{request_id}] ✅ Step 3 completed in {step_duration:.2f}ms")
        except Exception as e:
            logger.error(f"[{request_id}] ❌ Step 3 failed: Channel lookup error: {str(e)}", exc_info=True)
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': f"❌ Failed to lookup channel #{channel_name}.\n\nThis might be due to:\n" +
                       "• Network connectivity issues\n" +
                       "• Invalid Slack API token\n" +
                       "• SSL certificate issues\n\n" +
                       f"Technical error: {str(e)[:100]}"
            })
        
        if not channel_id:
            logger.info(f"[{request_id}] ❌ Channel not found: {channel_name}")
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': f"❌ I couldn't find the channel #{channel_name}.\n\n" +
                       "Please make sure:\n" +
                       "• The channel name is spelled correctly\n" +
                       "• The channel exists and is accessible\n" +
                       "• You have permission to view the channel"
            })
        
        logger.info(f"[{request_id}] Found channel ID: {channel_id}")
        
        # Step 4: Check bot membership
        step_start = time.time()
        logger.info(f"[{request_id}] 👤 Step 4: Checking bot membership in channel {channel_id}")
        
        try:
            is_member = slack_service.check_bot_membership(channel_id)
            step_duration = (time.time() - step_start) * 1000
            logger.info(f"[{request_id}] ✅ Step 4 completed in {step_duration:.2f}ms")
        except Exception as e:
            logger.error(f"[{request_id}] ❌ Step 4 failed: Membership check error: {str(e)}", exc_info=True)
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': f"❌ Failed to check bot membership in #{channel_name}.\n\n" +
                       f"Technical error: {str(e)[:100]}"
            })
        
        if not is_member:
            logger.info(f"[{request_id}] ❌ Bot not a member of channel {channel_id}")
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': f"❌ I need to be added to #{channel_name} first.\n\n" +
                       f"Please type `/invite @SlackOpsBot` in #{channel_name}, " +
                       "then try the summary command again."
            })
        
        logger.info(f"[{request_id}] Bot is a member of channel {channel_id}")
        
        # Step 5: Fetch messages
        step_start = time.time()
        logger.info(f"[{request_id}] 📥 Step 5: Fetching messages from channel {channel_id}")
        
        try:
            messages = slack_service.fetch_channel_messages(channel_id, hours_back=24)
            step_duration = (time.time() - step_start) * 1000
            logger.info(f"[{request_id}] ✅ Step 5 completed in {step_duration:.2f}ms")
        except Exception as e:
            logger.error(f"[{request_id}] ❌ Step 5 failed: Message fetch error: {str(e)}", exc_info=True)
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': f"❌ Failed to fetch messages from #{channel_name}.\n\n" +
                       f"Technical error: {str(e)[:100]}"
            })
        
        if not messages:
            logger.info(f"[{request_id}] 📭 No messages found in channel {channel_id}")
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': f"📭 No messages found in #{channel_name} in the last 24 hours.\n\n" +
                       "The channel appears to be quiet recently. " +
                       "Try again when there's more activity!"
            })
        
        logger.info(f"[{request_id}] Fetched {len(messages)} messages")
        
        # Step 6: Enrich messages
        step_start = time.time()
        logger.info(f"[{request_id}] 👥 Step 6: Enriching messages with user information")
        
        try:
            enriched_messages = slack_service.enrich_messages_with_usernames(messages)
            step_duration = (time.time() - step_start) * 1000
            logger.info(f"[{request_id}] ✅ Step 6 completed in {step_duration:.2f}ms")
        except Exception as e:
            logger.error(f"[{request_id}] ❌ Step 6 failed: Message enrichment error: {str(e)}", exc_info=True)
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': f"❌ Failed to enrich messages with user information.\n\n" +
                       f"Technical error: {str(e)[:100]}"
            })
        
        if not enriched_messages:
            logger.info(f"[{request_id}] 📭 No valid messages after enrichment")
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': f"📭 No valid messages found in #{channel_name} to summarize.\n\n" +
                       "The messages might be from bots or have other issues."
            })
        
        logger.info(f"[{request_id}] Enriched {len(enriched_messages)} messages with usernames")
        
        # Step 7: Generate summary with timeout protection
        step_start = time.time()
        logger.info(f"[{request_id}] 🤖 Step 7: Generating summary for {len(enriched_messages)} messages")
        
        # Check if we're approaching the 3-second Slack timeout
        total_elapsed = time.time() - start_time
        if total_elapsed > 2.5:  # 2.5 seconds safety margin
            logger.warning(f"[{request_id}] ⏰ Approaching timeout ({total_elapsed:.2f}s), returning quick summary")
            summary = f"📊 **Quick Summary for #{channel_name}**\n\n" + \
                     f"✅ Found {len(enriched_messages)} messages from {len(set(msg['username'] for msg in enriched_messages))} users in the last 24 hours.\n\n" + \
                     f"📝 Processing time exceeded limit for detailed AI analysis.\n" + \
                     f"💡 Try again for a detailed summary, or check a smaller/less active channel."
        else:
            try:
                summary = gemini_service.summarize_messages(enriched_messages, channel_name)
                step_duration = (time.time() - step_start) * 1000
                logger.info(f"[{request_id}] ✅ Step 7 completed in {step_duration:.2f}ms")
            except Exception as e:
                logger.error(f"[{request_id}] ❌ Step 7 failed: Summary generation error: {str(e)}", exc_info=True)
                # Generate a fallback summary
                summary = f"📊 **Summary for #{channel_name}**\n\n" + \
                         f"Found {len(enriched_messages)} messages in the last 24 hours, " + \
                         f"but AI summarization is currently unavailable.\n\n" + \
                         f"*Error: {str(e)[:100]}*"
        
        logger.info(f"[{request_id}] 🎉 Summary generated successfully")
        
        # Return the formatted summary
        return JsonResponse({
            'response_type': 'in_channel',
            'text': summary
        })
        
    except Exception as e:
        logger.error(f"[{request_id}] ❌ CRITICAL ERROR in handle_summary_command: {str(e)}", exc_info=True)
        
        # Always return a valid response to Slack
        return JsonResponse({
            'response_type': 'ephemeral',
            'text': f"❌ Sorry, there was an unexpected error generating the summary.\n\n" +
                   f"Please try again in a few moments. If the problem persists, " +
                   f"contact your workspace administrator.\n\n" +
                   f"Error reference: {request_id}"
        })

def handle_summary_command_background(text, user_name, request_id):
    """Handle summary command in background without timeout protection for full AI processing"""
    from ..services.slack_service import SlackService
    from ..services.gemini_service import GeminiService
    
    start_time = time.time()
    
    try:
        logger.info(f"[{request_id}] 🔄 Background processing: Parsing channel name")
        
        channel_name = parse_channel_name(text)
        if not channel_name:
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': '📝 Please specify a channel to summarize.'
            })
        
        logger.info(f"[{request_id}] 🔧 Background processing: Initializing services")
        slack_service = SlackService()
        gemini_service = GeminiService()
        
        logger.info(f"[{request_id}] 🔍 Background processing: Looking up channel ID for: {channel_name}")
        channel_id = slack_service.find_channel_id(channel_name)
        
        if not channel_id:
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': f"❌ I couldn't find the channel #{channel_name}."
            })
        
        logger.info(f"[{request_id}] 👤 Background processing: Checking bot membership")
        is_member = slack_service.check_bot_membership(channel_id)
        
        if not is_member:
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': f"❌ I need to be added to #{channel_name} first."
            })
        
        logger.info(f"[{request_id}] 📥 Background processing: Fetching messages")
        messages = slack_service.fetch_channel_messages(channel_id, hours_back=24)
        
        if not messages:
            return JsonResponse({
                'response_type': 'in_channel',
                'text': f"📭 No messages found in #{channel_name} in the last 24 hours."
            })
        
        logger.info(f"[{request_id}] 👥 Background processing: Enriching {len(messages)} messages")
        enriched_messages = slack_service.enrich_messages_with_usernames(messages)
        
        if not enriched_messages:
            return JsonResponse({
                'response_type': 'in_channel',
                'text': f"📭 No valid messages found in #{channel_name} to summarize."
            })
        
        logger.info(f"[{request_id}] 🤖 Background processing: Generating AI summary for {len(enriched_messages)} messages")
        
        # NO TIMEOUT PROTECTION HERE - let it run as long as needed
        summary = gemini_service.summarize_messages(enriched_messages, channel_name)
        
        total_elapsed = time.time() - start_time
        logger.info(f"[{request_id}] ✅ Background processing completed in {total_elapsed:.2f}s")
        
        return JsonResponse({
            'response_type': 'in_channel',
            'text': summary
        })
        
    except Exception as e:
        total_elapsed = time.time() - start_time
        logger.error(f"[{request_id}] ❌ Background processing error after {total_elapsed:.2f}s: {str(e)}", exc_info=True)
        
        return JsonResponse({
            'response_type': 'ephemeral',
            'text': f"❌ Sorry, there was an error generating the summary.\n\nError: {str(e)[:100]}..."
        })

def handle_unread_summary_command(text, user_name, user_id, request_id):
    """Handle the /unread command workflow to summarize only unread messages"""
    from ..services.slack_service import SlackService
    from ..services.gemini_service import GeminiService
    
    # Track overall start time for timeout protection
    start_time = time.time()
    step_start = time.time()
    
    try:
        logger.info(f"[{request_id}] 🔍 Unread Step 1: Parsing channel name")
        
        # Parse channel name from command text
        channel_name = parse_channel_name(text)
        logger.info(f"[{request_id}] Parsed channel name: '{channel_name}'")
        
        if not channel_name:
            logger.info(f"[{request_id}] ❌ No channel name provided for unread summary")
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': '📬 Please specify a channel to check for unread messages.\n\n' +
                       'Usage: `/unread #channel-name`\n' +
                       'Examples:\n' +
                       '• `/unread #general`\n' +
                       '• `/unread general`\n' +
                       '• `/unread #team-updates`'
            })
        
        step_duration = (time.time() - step_start) * 1000
        logger.info(f"[{request_id}] ✅ Unread Step 1 completed in {step_duration:.2f}ms")
        
        # Step 2: Initialize services
        step_start = time.time()
        logger.info(f"[{request_id}] 🔧 Unread Step 2: Initializing services")
        
        try:
            slack_service = SlackService()
            gemini_service = GeminiService()
            step_duration = (time.time() - step_start) * 1000
            logger.info(f"[{request_id}] ✅ Unread Step 2 completed in {step_duration:.2f}ms")
        except Exception as e:
            logger.error(f"[{request_id}] ❌ Unread Step 2 failed: Service initialization error: {str(e)}", exc_info=True)
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': f"❌ Service initialization failed. Please contact administrator.\nError: {str(e)[:100]}"
            })
        
        # Step 3: Find channel ID
        step_start = time.time()
        logger.info(f"[{request_id}] 🔍 Unread Step 3: Looking up channel ID for: {channel_name}")
        
        try:
            channel_id = slack_service.find_channel_id(channel_name)
            step_duration = (time.time() - step_start) * 1000
            logger.info(f"[{request_id}] ✅ Unread Step 3 completed in {step_duration:.2f}ms")
        except Exception as e:
            logger.error(f"[{request_id}] ❌ Unread Step 3 failed: Channel lookup error: {str(e)}", exc_info=True)
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': f"❌ Failed to lookup channel #{channel_name}.\n\nTechnical error: {str(e)[:100]}"
            })
        
        if not channel_id:
            logger.info(f"[{request_id}] ❌ Channel not found: {channel_name}")
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': f"❌ I couldn't find the channel #{channel_name}.\n\n" +
                       "Please make sure:\n" +
                       "• The channel name is spelled correctly\n" +
                       "• The channel exists and is accessible\n" +
                       "• You have permission to view the channel"
            })
        
        logger.info(f"[{request_id}] Found channel ID: {channel_id}")
        
        # Step 4: Check bot membership
        step_start = time.time()
        logger.info(f"[{request_id}] 👤 Unread Step 4: Checking bot membership in channel {channel_id}")
        
        try:
            is_member = slack_service.check_bot_membership(channel_id)
            step_duration = (time.time() - step_start) * 1000
            logger.info(f"[{request_id}] ✅ Unread Step 4 completed in {step_duration:.2f}ms")
        except Exception as e:
            logger.error(f"[{request_id}] ❌ Unread Step 4 failed: Membership check error: {str(e)}", exc_info=True)
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': f"❌ Failed to check bot membership in #{channel_name}.\n\nTechnical error: {str(e)[:100]}"
            })
        
        if not is_member:
            logger.info(f"[{request_id}] ❌ Bot not a member of channel {channel_id}")
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': f"❌ I need to be added to #{channel_name} first.\n\n" +
                       f"Please type `/invite @SlackOpsBot` in #{channel_name}, " +
                       "then try the unread command again."
            })
        
        logger.info(f"[{request_id}] Bot is a member of channel {channel_id}")
        
        # Step 5: Fetch unread messages
        step_start = time.time()
        logger.info(f"[{request_id}] 📥 Unread Step 5: Fetching unread messages from channel {channel_id} for user {user_id}")
        
        try:
            messages = slack_service.fetch_unread_messages(channel_id, user_id)
            step_duration = (time.time() - step_start) * 1000
            logger.info(f"[{request_id}] ✅ Unread Step 5 completed in {step_duration:.2f}ms")
        except Exception as e:
            logger.error(f"[{request_id}] ❌ Unread Step 5 failed: Unread message fetch error: {str(e)}", exc_info=True)
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': f"❌ Failed to fetch unread messages from #{channel_name}.\n\nTechnical error: {str(e)[:100]}"
            })
        
        if not messages:
            logger.info(f"[{request_id}] 📭 No unread messages found in channel {channel_id}")
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': f"📬 Great news! You have no unread messages in #{channel_name}.\n\n" +
                       "🎉 You're all caught up with recent activity!\n\n" +
                       "💡 If you expect unread messages, they might be older than 2 hours."
            })
        
        logger.info(f"[{request_id}] Fetched {len(messages)} unread messages")
        
        # Step 6: Enrich messages
        step_start = time.time()
        logger.info(f"[{request_id}] 👥 Unread Step 6: Enriching unread messages with user information")
        
        try:
            enriched_messages = slack_service.enrich_messages_with_usernames(messages)
            step_duration = (time.time() - step_start) * 1000
            logger.info(f"[{request_id}] ✅ Unread Step 6 completed in {step_duration:.2f}ms")
        except Exception as e:
            logger.error(f"[{request_id}] ❌ Unread Step 6 failed: Message enrichment error: {str(e)}", exc_info=True)
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': f"❌ Failed to enrich unread messages with user information.\n\nTechnical error: {str(e)[:100]}"
            })
        
        if not enriched_messages:
            logger.info(f"[{request_id}] 📭 No valid unread messages after enrichment")
            return JsonResponse({
                'response_type': 'ephemeral',
                'text': f"📬 No valid unread messages found in #{channel_name}.\n\n" +
                       "You're all caught up! 🎉"
            })
        
        logger.info(f"[{request_id}] Enriched {len(enriched_messages)} unread messages with usernames")
        
        # Step 7: Generate unread summary with timeout protection
        step_start = time.time()
        logger.info(f"[{request_id}] 🤖 Unread Step 7: Generating unread summary for {len(enriched_messages)} messages")
        
        # Check if we're approaching the 3-second Slack timeout
        total_elapsed = time.time() - start_time
        if total_elapsed > 2.5:  # 2.5 seconds safety margin
            logger.warning(f"[{request_id}] ⏰ Approaching timeout ({total_elapsed:.2f}s), returning quick unread summary")
            summary = f"📬 **Quick Unread Summary for #{channel_name}**\n\n" + \
                     f"✅ Found {len(enriched_messages)} unread messages from {len(set(msg['username'] for msg in enriched_messages))} users.\n\n" + \
                     f"📝 Processing time exceeded limit for detailed AI analysis.\n" + \
                     f"💡 Try again for a detailed unread summary."
        else:
            try:
                summary = gemini_service.summarize_unread_messages(enriched_messages, channel_name, user_name)
                step_duration = (time.time() - step_start) * 1000
                logger.info(f"[{request_id}] ✅ Unread Step 7 completed in {step_duration:.2f}ms")
            except Exception as e:
                logger.error(f"[{request_id}] ❌ Unread Step 7 failed: Unread summary generation error: {str(e)}", exc_info=True)
                # Generate a fallback summary
                summary = f"📬 **Unread Summary for #{channel_name}**\n\n" + \
                         f"Found {len(enriched_messages)} unread messages, " + \
                         f"but AI summarization is currently unavailable.\n\n" + \
                         f"*Error: {str(e)[:100]}*"
        
        logger.info(f"[{request_id}] 🎉 Unread summary generated successfully")
        
        # Return the formatted unread summary
        return JsonResponse({
            'response_type': 'ephemeral',  # Only visible to the user who requested it
            'text': summary
        })
        
    except Exception as e:
        logger.error(f"[{request_id}] ❌ CRITICAL ERROR in handle_unread_summary_command: {str(e)}", exc_info=True)
        
        # Always return a valid response to Slack
        return JsonResponse({
            'response_type': 'ephemeral',
            'text': f"❌ Sorry, there was an unexpected error generating your unread summary.\n\n" +
                   f"Please try again in a few moments. If the problem persists, " +
                   f"contact your workspace administrator.\n\n" +
                   f"Error reference: {request_id}"
        })

def parse_channel_name(text):
    """Parse channel name from command text, handling various formats"""
    if not text:
        return None
    
    # Clean up the text
    text = text.strip()
    
    # Handle formats: "#general", "general", or just whitespace
    if text.startswith('#'):
        channel_name = text[1:].strip()
    else:
        channel_name = text.strip()
    
    # Return None if empty after processing
    return channel_name if channel_name else None

def parse_summary_command(text):
    """
    Parse /summary command text for thread and channel support.
    Returns a dict with keys: type, channel, thread_type, etc.
    Supports:
      - /summary thread [message-link]
      - /summary thread [channel] [timestamp]
      - /summary thread latest [channel]
      - /summary all
      - /summary unread [channel]
      - /summary [channel]
    """
    if not text:
        return {"type": "channel", "channel": None}

    tokens = text.strip().split()
    if not tokens:
        return {"type": "channel", "channel": None}

    # Thread summary parsing
    if tokens[0] == "thread":
        # /summary thread latest [channel]
        if len(tokens) > 2 and tokens[1] == "latest":
            return {
                "type": "thread_latest",
                "channel": tokens[2].lstrip("#")
            }
        # /summary thread [message-link]
        if len(tokens) > 1:
            # Accept both raw and angle-bracketed links
            link_token = tokens[1]
            # Remove angle brackets if present
            if link_token.startswith("<") and link_token.endswith(">"):
                link_token = link_token[1:-1]
            link_match = re.match(r'https?://[^/]+/archives/([A-Z0-9]+)/p(\d{10,})', link_token)
            if link_match:
                channel_id = link_match.group(1)
                raw_ts = link_match.group(2)
                # Insert decimal before last 6 digits
                if len(raw_ts) > 6:
                    ts = f"{raw_ts[:-6]}.{raw_ts[-6:]}"
                else:
                    ts = raw_ts
                return {
                    "type": "thread_message_link",
                    "channel_id": channel_id,
                    "timestamp": ts
                }
        # /summary thread [channel] [timestamp]
        if len(tokens) > 2 and re.match(r'^[a-zA-Z0-9_\-]+$', tokens[1]) and re.match(r'^\d{10}(\.\d+)?$', tokens[2]):
            return {
                "type": "thread_channel_ts",
                "channel": tokens[1].lstrip("#"),
                "timestamp": tokens[2]
            }
        # /summary thread (no params)
        return {"type": "thread", "params": tokens[1:]}

    # /summary all
    if tokens[0] == "all":
        return {"type": "all"}
    # /summary unread [channel]
    if tokens[0] == "unread":
        if len(tokens) > 1:
            return {"type": "unread", "channel": tokens[1].lstrip("#")}
        else:
            return {"type": "unread", "channel": None}
    # /summary [channel]
    if tokens:
        return {"type": "channel", "channel": tokens[0].lstrip("#")}
    return {"type": "channel", "channel": None}