import logging
from typing import Dict, Optional, Tuple
from ..utils.intent_recognition import IntentRecognizer, Intent
from ..utils.conversation_state import ConversationStateManager
from ..services.slack_service import SlackService
from ..services.gemini_service import GeminiService
from ..utils.summary_utils import handle_summary_command, handle_unread_summary_command, parse_summary_command

logger = logging.getLogger(__name__)

class ConversationHandler:
    def __init__(self, slack_service: SlackService, gemini_service: GeminiService):
        self.intent_recognizer = IntentRecognizer()
        self.state_manager = ConversationStateManager()
        self.slack_service = slack_service
        self.gemini_service = gemini_service

    def handle_message(self, event: Dict) -> Optional[str]:
        """Handle an incoming message event"""
        user_id = event.get('user')
        text = event.get('text', '').strip()
        channel_id = event.get('channel')
        thread_ts = event.get('thread_ts')

        # Recognize intent
        intent_data = self.intent_recognizer.recognize_intent(text)
        intent = intent_data.get('intent')

        if intent == Intent.GREETING:
            return self.intent_recognizer.get_greeting_response()

        elif intent == Intent.CHANNEL_SUMMARY:
            channel_name = intent_data.get('channel')
            messages = self.slack_service.get_channel_messages(channel_id, channel_name)
            if not messages:
                return ":warning: I couldn't fetch messages from that channel. Make sure I have access to it!"

            summary = self.gemini_service.generate_summary(messages, channel_name)
            if summary:
                # Store context for follow-up questions
                self.state_manager.update_context(user_id, channel_name, channel_id, summary, messages)
                return summary.get('text', 'Sorry, I had trouble generating a summary.')
            return ":warning: I had trouble generating a summary. Please try again!"

        elif intent == Intent.THREAD_SUMMARY:
            if not thread_ts:
                return ":warning: This command works best in a thread! Please use `/summary thread` as a reply inside the thread you want to summarize, or use `/summary thread [message-link]`."
            
            messages = self.slack_service.get_thread_messages(channel_id, thread_ts)
            if not messages:
                return ":warning: I couldn't fetch messages from this thread!"

            summary = self.gemini_service.generate_summary(messages, "thread")
            if summary:
                # Store context for follow-up questions about the thread
                self.state_manager.update_context(user_id, "thread", channel_id, summary, messages, thread_ts=thread_ts)
                return summary.get('text', 'Sorry, I had trouble generating a summary.')
            return ":warning: I had trouble generating a summary. Please try again!"

        elif intent == Intent.FOLLOW_UP:
            context = self.state_manager.get_context(user_id)
            if not context or not context.is_context_valid():
                return ":thinking_face: I need some context first. Try asking for a channel or thread summary, then I can answer follow-up questions!"

            section_type = intent_data.get('section_type')
            if not section_type:
                return ":thinking_face: I'm not sure what specific information you're looking for. Try asking about contributors, urgent items, topics, decisions, or questions!"

            # Try to get the section from the stored summary first
            section_content = self.state_manager.extract_summary_section(user_id, section_type)
            if section_content:
                return f":mag: Here's what I found:\n{section_content}"

            # If not found in stored summary, generate a focused summary
            focused_summary = self.gemini_service.generate_focused_summary(
                context.last_messages,
                section_type,
                context.channel_name
            )
            if focused_summary:
                return focused_summary.get('text', ":warning: I couldn't find that information in the current context.")
            return ":warning: I had trouble analyzing that aspect of the conversation."

        elif intent == Intent.FEEDBACK:
            return ":smile: Thank you for your feedback! I'm constantly learning to serve you better."

        elif intent == Intent.HELP:
            return (
                ":robot_face: *Beta-Summarizer Commands Guide*\n\n"
                "*1. Channel Summaries*\n"
                "• `/summary #channel-name` - Get a summary of recent messages\n"
                "  Example: `/summary #general`\n"
                "• `/summary unread #channel-name` - See what you missed\n"
                "  Example: `/summary unread #team-updates`\n\n"
                "*2. Thread Summaries*\n"
                "• `/summary thread` - Summarize current thread (use in a thread)\n"
                "• `/summary thread latest #channel` - Summarize most recent thread\n"
                "  Example: `/summary thread latest #projects`\n\n"
                "*3. Multi-Channel Updates*\n"
                "• `/summary all` - Summarize all channels you have access to\n"
                "• `/summary unread` - Show unread messages in current channel\n\n"
                "*4. Follow-up Questions*\n"
                "After any summary, you can ask about:\n"
                "• `Who were the active participants?`\n"
                "• `What urgent items were discussed?`\n"
                "• `What decisions were made?`\n"
                "• `What are the main topics?`\n"
                "• `What questions are pending?`\n\n"
                "*:bulb: Pro Tips:*\n"
                "• Use in threads to focus on specific discussions\n"
                "• Natural language works! Just ask what you want to know\n"
                "• Summaries include context, decisions, and action items"
            )

        return ":thinking_face: I need some context first. Try asking for a channel or thread summary, then I can answer follow-up questions!"

    def handle_slash_command(self, command_data: Dict) -> Dict:
        """Handle slash commands, particularly thread-related ones"""
        try:
            command = command_data.get('command', '')
            text = command_data.get('text', '').strip()
            user_id = command_data.get('user_id')

            # Use improved parser for thread and channel summary commands
            parsed = parse_summary_command(text)
            if parsed["type"].startswith("thread"):
                # Route all thread commands to the thread handler
                return self._handle_thread_command(parsed, user_id)

            # Handle other commands using existing handlers
            return handle_summary_command(text, user_id, 'cmd')

        except Exception as e:
            logger.error(f"Error handling slash command: {str(e)}", exc_info=True)
            return {
                'response_type': 'ephemeral',
                'text': "Sorry, I encountered an error processing your command."
            }

    def _handle_greeting(self) -> Dict:
        """Handle greeting intent with a friendly response"""
        return {
            'text': "Hello! 👋 I'm SlackOpsBot, your AI-powered assistant. I can help you catch up on channels and threads. What would you like to know?"
        }

    def _handle_channel_summary(self, channel_name: str, user_id: str) -> Dict:
        """Handle channel summary requests"""
        try:
            # Send immediate response
            immediate_response = {
                'text': f":zap: **Processing summary for #{channel_name}...**\n\n" +
                       f":robot_face: AI analysis starting now with full OAuth permissions.\n" +
                       f":bar_chart: Fetching messages and generating intelligent summary.\n" +
                       f":stopwatch: This usually takes 10-30 seconds for detailed analysis.\n\n" +
                       f":sparkles: **Full AI-powered summary will appear shortly!**"
            }

            channel_id = self.slack_service.find_channel_id(channel_name)
            if not channel_id:
                return {
                    'text': f":x: I couldn't find the channel #{channel_name}. Make sure it exists and I have access to it."
                }

            # Check bot membership
            if not self.slack_service.check_bot_membership(channel_id):
                return {
                    'text': f":warning: I need to be invited to #{channel_name} first. Please type `/invite @SlackOpsBot` in #{channel_name} and try again."
                }

            # Get messages and generate summary
            messages = self.slack_service.fetch_channel_messages(channel_id)
            if not messages:
                return {
                    'text': f":information_source: No messages found in #{channel_name} in the last 24 hours."
                }

            enriched_messages = self.slack_service.enrich_messages_with_usernames(messages)
            summary = self.gemini_service.summarize_messages(enriched_messages, channel_name)
            
            return {
                'text': summary,
                'replace_original': True
            }

        except Exception as e:
            logger.error(f"Error handling channel summary: {str(e)}", exc_info=True)
            return {
                'text': f":x: Sorry, I encountered an error summarizing #{channel_name}.\n\nError: {str(e)[:100]}"
            }

    def _handle_thread_summary(self, channel_id: str, topic: Optional[str], thread_ts: Optional[str]) -> Dict:
        """Handle thread summary requests"""
        try:
            if thread_ts:
                messages = self.slack_service.fetch_thread_messages(channel_id, thread_ts)
                if messages:
                    enriched_messages = self.slack_service.enrich_messages_with_usernames(messages)
                    summary = self.gemini_service.summarize_thread(enriched_messages, topic)
                    return {'text': summary}
            
            elif topic:
                thread = self.slack_service.find_thread_by_topic(channel_id, topic)
                if thread:
                    messages = self.slack_service.fetch_thread_messages(channel_id, thread['thread_ts'])
                    if messages:
                        enriched_messages = self.slack_service.enrich_messages_with_usernames(messages)
                        summary = self.gemini_service.summarize_thread(enriched_messages, topic)
                        return {'text': summary}
                    
                return {
                    'text': f":mag: I couldn't find any messages in the thread about '{topic}'."
                }
            
            return {
                'text': ":question: I couldn't find the thread you're looking for. Try being more specific or provide a message link."
            }

        except Exception as e:
            logger.error(f"Error handling thread summary: {str(e)}", exc_info=True)
            return {
                'text': ":x: Sorry, I encountered an error summarizing the thread."
            }

    def _handle_thread_command(self, thread_params: dict, user_id: str) -> dict:
        """Handle thread-specific slash commands"""
        try:
            # Send immediate response
            immediate_response = {
                'response_type': 'ephemeral',
                'text': ":zap: Processing thread summary...\n" +
                       "This will take just a moment!"
            }

            # /summary thread [message-link]
            if thread_params.get('type') == 'thread_message_link':
                channel_id = thread_params['channel_id']
                thread_ts = thread_params['timestamp']
                messages = self.slack_service.fetch_thread_messages(channel_id, thread_ts)
                if not messages:
                    return {
                        'response_type': 'ephemeral',
                        'text': ":information_source: No messages found in the specified thread."
                    }
                enriched_messages = self.slack_service.enrich_messages_with_usernames(messages)
                summary = self.gemini_service.summarize_thread(enriched_messages)
                return {
                    'response_type': 'in_channel',
                    'text': summary,
                    'replace_original': True
                }

            # /summary thread latest [channel]
            if thread_params.get('type') == 'thread_latest':
                channel_name = thread_params['channel']
                channel_id = self.slack_service.find_channel_id(channel_name)
                if not channel_id:
                    return {
                        'response_type': 'ephemeral',
                        'text': f":x: Channel #{channel_name} not found."
                    }
                latest_thread = self.slack_service.find_latest_thread(channel_id)
                if not latest_thread:
                    return {
                        'response_type': 'ephemeral',
                        'text': f":information_source: No recent threads found in #{channel_name}."
                    }
                messages = self.slack_service.fetch_thread_messages(channel_id, latest_thread['thread_ts'])
                if not messages:
                    return {
                        'response_type': 'ephemeral',
                        'text': ":information_source: No messages found in the specified thread."
                    }
                enriched_messages = self.slack_service.enrich_messages_with_usernames(messages)
                summary = self.gemini_service.summarize_thread(enriched_messages)
                return {
                    'response_type': 'in_channel',
                    'text': summary,
                    'replace_original': True
                }

            # /summary thread [channel] [timestamp]
            if thread_params.get('type') == 'thread_channel_ts':
                channel_name = thread_params['channel']
                thread_ts = thread_params['timestamp']
                channel_id = self.slack_service.find_channel_id(channel_name)
                if not channel_id:
                    return {
                        'response_type': 'ephemeral',
                        'text': f":x: Channel #{channel_name} not found."
                    }
                messages = self.slack_service.fetch_thread_messages(channel_id, thread_ts)
                if not messages:
                    return {
                        'response_type': 'ephemeral',
                        'text': ":information_source: No messages found in the specified thread."
                    }
                enriched_messages = self.slack_service.enrich_messages_with_usernames(messages)
                summary = self.gemini_service.summarize_thread(enriched_messages)
                return {
                    'response_type': 'in_channel',
                    'text': summary,
                    'replace_original': True
                }

            # fallback: /summary thread (no params)
            return {
                'response_type': 'ephemeral',
                'text': ":x: Invalid thread command format. Use one of:\n"
                        "• `/summary thread [message-link]`\n"
                        "• `/summary thread [channel] [timestamp]`\n"
                        "• `/summary thread latest [channel]`"
            }

        except Exception as e:
            logger.error(f"Error handling thread command: {str(e)}", exc_info=True)
            return {
                'response_type': 'ephemeral',
                'text': ":x: Sorry, I encountered an error processing the thread command."
            }