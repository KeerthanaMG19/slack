from enum import Enum
import re
from typing import Dict, Optional, Tuple

# Intent types
class Intent(Enum):
    GREETING = "greeting"
    CHANNEL_SUMMARY = "channel_summary"
    THREAD_SUMMARY = "thread_summary"
    FOLLOW_UP = "follow_up"
    FEEDBACK = "feedback"
    HELP = "help"
    UNKNOWN = "unknown"

class IntentRecognizer:
    def __init__(self):
        self.greeting_patterns = [
            r"^(hi|hello|hey|good morning|good afternoon|good evening)[\s!]*$"
        ]
        
        self.channel_summary_patterns = [
            r"what'?s\s+happening\s+in\s+[#]?(?P<channel>[\w-]+)",
            r"summarize\s+[#]?(?P<channel>[\w-]+)",
            r"update\s+on\s+[#]?(?P<channel>[\w-]+)",
            r"what'?s\s+new\s+in\s+[#]?(?P<channel>[\w-]+)",
            r"what'?s\s+going\s+on\s+in\s+[#]?(?P<channel>[\w-]+)"
        ]

        self.thread_summary_patterns = [
            r"summarize\s+thread",
            r"thread\s+summary",
            r"what'?s\s+happening\s+in\s+this\s+thread",
            r"what'?s\s+this\s+thread\s+about"
        ]

        self.follow_up_patterns = {
            'contributors': [
                r"who\s+(is|are|were)\s+(the\s+)?(most\s+)?(active|contributing)",
                r"active\s+contributors",
                r"who\s+contributed",
                r"who'?s\s+active",
                r"who'?s\s+participating"
            ],
            'urgent': [
                r"urgent\s+items",
                r"what'?s\s+urgent",
                r"what\s+needs\s+attention",
                r"what'?s\s+important",
                r"what\s+are\s+the\s+urgent\s+items",
                r"what'?s\s+critical"
            ],
            'topics': [
                r"what\s+(topics|was|were)\s+discussed",
                r"main\s+topics",
                r"key\s+topics",
                r"what\s+did\s+they\s+talk\s+about",
                r"what'?s\s+being\s+discussed"
            ],
            'decisions': [
                r"what\s+(decisions|actions)\s+were\s+made",
                r"any\s+decisions",
                r"what\s+was\s+decided",
                r"what\s+are\s+the\s+next\s+steps",
                r"action\s+items"
            ],
            'questions': [
                r"what\s+questions\s+were\s+asked",
                r"open\s+questions",
                r"what\s+needs\s+answers",
                r"unresolved\s+questions",
                r"what'?s\s+unclear"
            ]
        }

    def recognize_intent(self, text: str) -> Dict:
        """Recognize the intent of the input text"""
        text = text.lower().strip()

        # Check for greetings
        for pattern in self.greeting_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return {'intent': Intent.GREETING}

        # Check for channel summaries
        for pattern in self.channel_summary_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return {
                    'intent': Intent.CHANNEL_SUMMARY,
                    'channel': match.group('channel')
                }

        # Check for thread summaries
        for pattern in self.thread_summary_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return {'intent': Intent.THREAD_SUMMARY}

        # Check for follow-up questions
        for section_type, patterns in self.follow_up_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return {
                        'intent': Intent.FOLLOW_UP,
                        'section_type': section_type
                    }

        # Check for feedback
        if "feedback" in text:
            return {'intent': Intent.FEEDBACK}

        # Check for help
        if text in ["help", "what can you do", "how do you work"]:
            return {'intent': Intent.HELP}

        return {'intent': Intent.UNKNOWN}

    def get_greeting_response(self) -> str:
        """Return a friendly greeting response"""
        return ":wave: Hello! I'm here to help summarize channels and threads. What would you like to know?"

    def parse_thread_command(self, text: str) -> Optional[Dict]:
        """
        Parse thread-specific commands like:
        /summary thread [message-link]
        /summary thread [channel] [timestamp]
        /summary thread latest [channel]
        """
        # Remove '/summary thread' from the start if present
        text = re.sub(r'^/summary\s+thread\s+', '', text.strip(), flags=re.IGNORECASE)
        text = text.strip()

        # Try to match message link format
        link_match = re.match(r'https?://[^/]+/archives/([A-Z0-9]+)/p(\d{10,})', text)
        if link_match:
            return {
                'type': 'message_link',
                'channel_id': link_match.group(1),
                'timestamp': link_match.group(2)
            }

        # Try to match channel timestamp format
        channel_ts_match = re.match(r'#?([a-zA-Z0-9_\-]+)\s+(\d{10,})', text)
        if channel_ts_match:
            return {
                'type': 'channel_timestamp',
                'channel': channel_ts_match.group(1),
                'timestamp': channel_ts_match.group(2)
            }

        # Try to match latest thread format: "latest [channel]"
        latest_match = re.match(r'latest\s+#?([a-zA-Z0-9_\-]+)', text)
        if latest_match:
            return {
                'type': 'latest',
                'channel': latest_match.group(1)
            }

        # If only "thread" is present, treat as current thread (no params)
        if text == "" or text.lower() == "thread":
            return {
                'type': 'current'
            }

        return None

    def get_help_message(self) -> str:
        return """Hello! 👋 I'm SlackOpsBot, your AI-powered channel and thread summarizer.

📊 *Channel Summaries*
• "What's happening in #channel"
• "Summarize #channel"
• "Update me on #channel"
• "Catch me up on #channel"

🧵 *Thread Summaries*
• "Show me the thread about [topic]"
• "/summary thread [message-link]"
• "/summary thread [channel] [timestamp]"
• "/summary thread latest [channel]"

💡 *Tips*
• You can use natural language to ask for summaries
• For threads, you can use message links or timestamps
• Use "help" anytime to see this message again

Need anything specific? Just ask! I'm here to help you stay updated."""