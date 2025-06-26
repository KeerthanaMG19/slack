import logging
from datetime import datetime
import google.generativeai as genai
from django.conf import settings
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class GeminiService:
    """Service class for interacting with Google Gemini AI"""

    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    # ---------------------------- PUBLIC METHODS ----------------------------

    def summarize_messages(self, messages, channel_name):
        """Summarize Slack channel messages using Gemini AI"""
        if not messages:
            return self._fallback_summary(messages, channel_name)

        try:
            formatted = self._format_messages(messages)
            prompt = self._build_summary_prompt(formatted, channel_name, len(messages))
            summary = self._get_ai_response(prompt)

            if summary:
                return self._wrap_summary(summary, channel_name, len(messages))
            else:
                return self._fallback_summary(messages, channel_name)

        except Exception as e:
            logger.error(f"Error generating summary from Gemini: {str(e)}")
            return self._fallback_summary(messages, channel_name)

    def summarize_unread_messages(self, messages, channel_name, user_name):
        """Summarize unread Slack messages for a specific user"""
        if not messages:
            return self._fallback_unread_summary(messages, channel_name, user_name)

        try:
            formatted = self._format_messages(messages)
            prompt = self._build_unread_summary_prompt(formatted, channel_name, len(messages), user_name)
            summary = self._get_ai_response(prompt)

            if summary:
                return self._wrap_unread_summary(summary, channel_name, len(messages), user_name)
            else:
                return self._fallback_unread_summary(messages, channel_name, user_name)

        except Exception as e:
            logger.error(f"Error generating unread summary from Gemini: {str(e)}")
            return self._fallback_unread_summary(messages, channel_name, user_name)

    def generate_response(self, prompt, context=None):
        """Generate a response using Gemini AI"""
        try:
            full_prompt = f"Context: {context}\n\nUser: {prompt}" if context else prompt
            return self._get_ai_response(full_prompt)
        except Exception as e:
            logger.error(f"Error generating response from Gemini: {str(e)}")
            raise

    def generate_summary(self, messages: List[Dict], channel_name: str = None) -> Optional[Dict]:
        """Generate a summary of messages"""
        if not messages:
            return None

        try:
            formatted_messages = self._format_messages(messages)
            
            prompt = f"""
            Please analyze these Slack messages and provide a summary in EXACTLY this format, with NO DEVIATION:

            Summary Report – #{channel_name or 'channel'}

            Key Topics

            • [First key topic with period.]

            • [Second key topic with period.]

            • [Third key topic with period.]

            Decisions & Actions

            • [First decision/action with period.]

            • [Second decision/action with period.]

            Status & Questions

            • Current Status: [One line status with period.]

            • Open Questions: [Key questions with question marks?]

            Contributors

            • [One line about participant count with period.]

            Needs Immediate Attention 🚨

            • [First urgent item with period.]

            • [Second urgent item with period.]

            Summary Details
            Messages analyzed: {len(messages)}
            Timeframe: Last 24 hours
            Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}

            CRITICAL FORMATTING RULES:
            1. Use ONLY the bullet character "•" (not emojis, dashes, or asterisks)
            2. Add exactly one line break after each bullet point
            3. End each bullet point with proper punctuation (period or question mark)
            4. Keep section titles EXACTLY as shown (no emojis except 🚨 in "Needs Immediate Attention")
            5. Use exactly two line breaks between sections
            6. Keep all formatting and spacing exactly as shown
            7. Do not add any additional sections or formatting
            8. Do not use any emojis except 🚨 in the "Needs Immediate Attention" section title

            MESSAGES TO ANALYZE:
            {formatted_messages}
            """

            response = self.model.generate_content(prompt)
            return {'text': response.text}

        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return None

    def generate_focused_summary(self, messages: List[Dict], focus_type: str, context: str = None) -> Optional[Dict]:
        """Generate a focused summary based on specific questions"""
        if not messages:
            return None

        try:
            formatted_messages = self._format_messages(messages)
            
            focus_prompts = {
                'contributors': """
                    Return exactly one bullet point about participant count and engagement.
                    Format:
                    • [Number] users actively involved in the discussion.
                    """,
                'urgent': """
                    Return 1-2 bullet points about urgent items.
                    Format:
                    • [First urgent item with period.]
                    • [Second urgent item with period.]
                    """,
                'topics': """
                    Return 2-3 bullet points about main topics.
                    Format:
                    • [First topic with period.]
                    • [Second topic with period.]
                    • [Third topic with period.]
                    """,
                'decisions': """
                    Return 1-2 bullet points about decisions/actions.
                    Format:
                    • [First decision with period.]
                    • [Second decision with period.]
                    """,
                'questions': """
                    Return exactly these two bullet points:
                    • Current Status: [One line status with period.]
                    • Open Questions: [Key questions with question marks?]
                    """
            }

            context_str = f" in {context}" if context else ""
            prompt = f"""
            Please analyze these Slack messages{context_str} focusing on {focus_type}.
            {focus_prompts.get(focus_type, '')}
            
            IMPORTANT:
            1. Use bullet points with the exact bullet character "•"
            2. Add a line break after each point
            3. End each point with proper punctuation
            4. Keep formatting exactly as shown
            """

            response = self.model.generate_content(prompt)
            return {'text': response.text}

        except Exception as e:
            logger.error(f"Error generating focused summary: {str(e)}")
            return None

    def answer_question(self, question, context=None):
        """Answer a specific question with optional context"""
        try:
            prompt = f"Context: {context}\n\nQuestion: {question}" if context else f"Question: {question}"
            return self._get_ai_response(prompt)
        except Exception as e:
            logger.error(f"Error answering question: {str(e)}")
            raise

    def summarize_thread(self, messages, thread_topic=None):
        """Summarize a Slack thread using Gemini AI"""
        if not messages:
            return self._fallback_thread_summary(messages, thread_topic)

        try:
            formatted = self._format_messages(messages)
            prompt = self._build_thread_summary_prompt(formatted, thread_topic, len(messages))
            summary = self._get_ai_response(prompt)

            if summary:
                return self._wrap_thread_summary(summary, thread_topic, len(messages))
            else:
                return self._fallback_thread_summary(messages, thread_topic)

        except Exception as e:
            logger.error(f"Error generating thread summary from Gemini: {str(e)}")
            return self._fallback_thread_summary(messages, thread_topic)

    # ---------------------------- INTERNAL HELPERS ----------------------------

    def _get_ai_response(self, prompt):
        try:
            response = self.model.generate_content(prompt)
            if response and response.text:
                return response.text.strip()
            logger.error("Empty response from Gemini")
            return None
        except Exception as e:
            logger.error(f"Error getting AI response: {str(e)}")
            return None

    def _format_messages(self, messages: List[Dict]) -> str:
        """Format messages for the prompt"""
        formatted = []
        for msg in messages:
            user = msg.get('user', 'Unknown')
            text = msg.get('text', '')
            ts = msg.get('ts', '')
            formatted.append(f"{user} ({ts}): {text}")
        return "\n".join(formatted)

    def _build_summary_prompt(self, messages, channel_name, count):
        return f"""Please analyze and summarize the following Slack channel conversation from #{channel_name}.

CONVERSATION DATA:
{chr(10).join(messages)}

FORMATTING REQUIREMENTS:
Use EXACTLY this format with NO DEVIATION:

Summary Report – #{channel_name}

Key Topics

• [First key topic with period.]

• [Second key topic with period.]

• [Third key topic with period.]

Decisions & Actions

• [First decision/action with period.]

• [Second decision/action with period.]

Status & Questions

• Current Status: [One line status with period.]

• Open Questions: [Key questions with question marks?]

Contributors

• [One line about participant count with period.]

Needs Immediate Attention 🚨

• [First urgent item with period.]

• [Second urgent item with period.]

Summary Details
Messages analyzed: {count}
Timeframe: Last 24 hours
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}

CRITICAL FORMATTING RULES:
1. Use ONLY the bullet character "•" (not emojis, dashes, or asterisks)
2. Add exactly one line break after each bullet point
3. End each bullet point with proper punctuation (period or question mark)
4. Keep section titles EXACTLY as shown (no emojis except 🚨 in "Needs Immediate Attention")
5. Use exactly two line breaks between sections
6. Keep all formatting and spacing exactly as shown
7. Do not add any additional sections or formatting
8. Do not use any emojis except 🚨 in the "Needs Immediate Attention" section title"""

    def _build_unread_summary_prompt(self, messages, channel_name, count, user):
        return f"""Please analyze and summarize the following UNREAD messages from #{channel_name} for @{user}.

UNREAD CONVERSATION DATA:
{chr(10).join(messages)}

FORMATTING REQUIREMENTS:
- Use emoji bullet points (🔹)
- Use bold headers
- Be concise and actionable
- Focus on missed content for @{user}

ANALYSIS INSTRUCTIONS:
1. Main topics
2. Mentions of @{user}
3. Actions impacting @{user}
4. Questions needing response
5. Urgent items
6. Ongoing discussion status

RESPONSE FORMAT:
📬 Unread Messages Summary for #{channel_name}

📋 What You Missed:
🔹 ...

👤 Mentions & Responses:
🔹 ...

⚡ Action Items & Decisions:
🔹 ...

❓ Questions Needing Attention:
🔹 ...

🚨 Urgent Items:
🔹 ...

💬 Current Discussion Status:
🔹 ...

CONTEXT:
- Channel: #{channel_name}
- Unread messages: {count}
- User: @{user}
- Time period: Recent activity"""

    def _build_thread_summary_prompt(self, messages, thread_topic, count):
        topic_context = f"about {thread_topic}" if thread_topic else ""
        
        return f"""Please analyze and summarize this Slack thread {topic_context}.

THREAD MESSAGES:
{chr(10).join(messages)}

FORMATTING REQUIREMENTS:
- Use emoji bullet points (🔹)
- Use bold for headers
- Be concise but thorough
- Highlight key points and decisions

ANALYSIS INSTRUCTIONS:
1. Main discussion points
2. Key decisions or conclusions
3. Action items or next steps
4. Unresolved questions
5. Participant contributions

RESPONSE FORMAT:
🧵 Thread Summary:
🔹 ...

⚡ Key Points & Decisions:
🔹 ...

📋 Action Items:
🔹 ...

❓ Open Questions:
🔹 ...

👥 Participant Insights:
🔹 ...

CONTEXT:
- Messages analyzed: {count}
- Topic: {thread_topic or 'Not specified'}"""

    # ---------------------------- FORMATTERS ----------------------------

    def _wrap_summary(self, summary, channel_name, count):
        """Format the final summary output"""
        return summary

    def _wrap_unread_summary(self, summary, channel_name, count, user):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        return f"""{summary}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 Catch-up Report: {count} unread messages analyzed
👤 Personalized for: @{user}
🤖 AI Analysis: Generated on {timestamp}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    def _wrap_thread_summary(self, summary, thread_topic, count):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        topic_display = f" about {thread_topic}" if thread_topic else ""
        
        return f"""🧵 **Thread Summary{topic_display}**

{summary}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 Analysis Details: {count} messages | Generated {timestamp}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    # ---------------------------- FALLBACKS ----------------------------

    def _fallback_summary(self, messages, channel_name):
        if not messages:
            return f"""📊 **Summary Report for #{channel_name}**

📋 Channel Status:
🔹 No messages found in the last 24 hours
🔹 Channel appears inactive

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 Report Details: No recent activity
🤖 AI Analysis: Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

        users = {msg['username'] for msg in messages}
        return f"""📊 **Summary Report for #{channel_name}**

📋 Activity Overview:
🔹 {len(messages)} messages exchanged
🔹 {len(users)} team members participated
🔹 Contributors: {', '.join(list(users)[:5])}{'...' if len(users) > 5 else ''}

📝 Recent Activity:
{self._recent_messages_preview(messages[:3])}

⚠️ Note: AI summarization temporarily unavailable

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 Report Details: {len(messages)} messages analyzed
🤖 AI Analysis: Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    def _fallback_unread_summary(self, messages, channel_name, user):
        if not messages:
            return f"""📬 **Unread Messages Summary for #{channel_name}**

📋 Current Status:
🔹 No unread messages in last 2 hours
🔹 You're all caught up!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 Catch-up Report: No unread messages
👤 Personalized for: @{user}
🤖 AI Analysis: Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

        users = {msg['username'] for msg in messages if msg.get('username')}
        return f"""📬 Unread Messages Summary for #{channel_name}

📋 What You Missed:
🔹 {len(messages)} new messages
🔹 {len(users)} active team members
🔹 Contributors: {', '.join(list(users)[:5])}{'...' if len(users) > 5 else ''}

**📝 Recent Activity:**
{self._recent_messages_preview(messages[:3])}

**⚠️ Note:** AI summarization temporarily unavailable

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 Catch-up Report: {len(messages)} unread messages analyzed
👤 Personalized for: @{user}
🤖 AI Analysis: Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    def _fallback_thread_summary(self, messages, thread_topic):
        """Generate a basic summary when AI processing fails"""
        if not messages:
            return "📭 No messages found in this thread."

        participants = len(set(msg.get('username', '') for msg in messages))
        topic_display = f" about {thread_topic}" if thread_topic else ""
        
        return f"""🧵 **Thread Summary{topic_display}**

📊 Basic Statistics:
🔹 {len(messages)} messages in the thread
🔹 {participants} participants involved
🔹 Latest activity: {messages[-1].get('timestamp').strftime("%Y-%m-%d %H:%M")}

💡 For a more detailed summary, please try again in a moment."""

    def _recent_messages_preview(self, messages):
        if not messages:
            return "🔹 No recent messages to display"

        lines = []
        for msg in messages:
            time_str = msg['timestamp'].strftime("%H:%M")
            text = msg['text'][:50] + ('...' if len(msg['text']) > 50 else '')
            lines.append(f"🔹 [{time_str}] @{msg['username']}: {text}")
        return '\n'.join(lines)
