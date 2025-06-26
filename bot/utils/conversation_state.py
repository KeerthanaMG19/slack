from typing import Dict, List, Optional
from datetime import datetime, timedelta
import re

class ConversationContext:
    def __init__(self, channel_name: str, channel_id: str, last_summary: Dict, last_messages: List[Dict], thread_ts: Optional[str] = None):
        self.channel_name = channel_name
        self.channel_id = channel_id
        self.last_summary = last_summary
        self.last_messages = last_messages
        self.thread_ts = thread_ts
        self.timestamp = datetime.now()

    def is_context_valid(self) -> bool:
        """Check if the context is still valid (within 5 minutes)"""
        return datetime.now() - self.timestamp < timedelta(minutes=5)

class ConversationStateManager:
    def __init__(self):
        self.contexts = {}  # user_id -> ConversationContext
        self.section_patterns = {
            'contributors': [
                r"(?s).*?Most Active Contributors:.*?\n(.*?)(?:\n\n|\n(?=[A-Z])|$)",
                r"(?s).*?Active Contributors:.*?\n(.*?)(?:\n\n|\n(?=[A-Z])|$)",
                r"(?s).*?Contributors:.*?\n(.*?)(?:\n\n|\n(?=[A-Z])|$)"
            ],
            'urgent': [
                r"(?s).*?Urgent Items:.*?\n(.*?)(?:\n\n|\n(?=[A-Z])|$)",
                r"(?s).*?Critical Items:.*?\n(.*?)(?:\n\n|\n(?=[A-Z])|$)",
                r"(?s).*?Priority Items:.*?\n(.*?)(?:\n\n|\n(?=[A-Z])|$)"
            ],
            'topics': [
                r"(?s).*?Key Topics Discussed:.*?\n(.*?)(?:\n\n|\n(?=[A-Z])|$)",
                r"(?s).*?Main Topics:.*?\n(.*?)(?:\n\n|\n(?=[A-Z])|$)",
                r"(?s).*?Topics:.*?\n(.*?)(?:\n\n|\n(?=[A-Z])|$)"
            ],
            'decisions': [
                r"(?s).*?Important Decisions & Actions:.*?\n(.*?)(?:\n\n|\n(?=[A-Z])|$)",
                r"(?s).*?Decisions Made:.*?\n(.*?)(?:\n\n|\n(?=[A-Z])|$)",
                r"(?s).*?Actions:.*?\n(.*?)(?:\n\n|\n(?=[A-Z])|$)"
            ],
            'questions': [
                r"(?s).*?Questions & Status:.*?\n(.*?)(?:\n\n|\n(?=[A-Z])|$)",
                r"(?s).*?Open Questions:.*?\n(.*?)(?:\n\n|\n(?=[A-Z])|$)",
                r"(?s).*?Questions:.*?\n(.*?)(?:\n\n|\n(?=[A-Z])|$)"
            ]
        }
        self.states = {}
        self.last_summaries = {}
        self.current_focus = {}

    def update_context(self, user_id: str, channel_name: str, channel_id: str, summary: Dict, messages: List[Dict], thread_ts: Optional[str] = None) -> None:
        """Update the conversation context for a user"""
        self.contexts[user_id] = ConversationContext(
            channel_name=channel_name,
            channel_id=channel_id,
            last_summary=summary,
            last_messages=messages,
            thread_ts=thread_ts
        )

    def get_context(self, user_id: str) -> Optional[ConversationContext]:
        """Get the current conversation context for a user"""
        context = self.contexts.get(user_id)
        if context and context.is_context_valid():
            return context
        return None

    def extract_summary_section(self, user_id: str, section_type: str) -> Optional[str]:
        """Extract a specific section from the stored summary"""
        context = self.get_context(user_id)
        if not context or not context.last_summary:
            return None

        summary_text = context.last_summary.get('text', '')
        if not summary_text:
            return None

        # Map section types to their headers in the summary
        section_headers = {
            'contributors': ['Contributors'],
            'urgent': ['Needs Immediate Attention 🚨'],
            'topics': ['Key Topics'],
            'decisions': ['Decisions & Actions'],
            'questions': ['Status & Questions']
        }

        # Try each possible header for the section
        headers = section_headers.get(section_type, [])
        for header in headers:
            if header in summary_text:
                # Find the section content
                start_idx = summary_text.find(header) + len(header)
                
                # Find the next section header or end of summary
                next_idx = float('inf')
                for all_headers in section_headers.values():
                    for h in all_headers:
                        idx = summary_text.find(h, start_idx)
                        if idx != -1 and idx < next_idx:
                            next_idx = idx
                
                # Extract the section content
                if next_idx == float('inf'):
                    content = summary_text[start_idx:].split('Summary Details')[0].strip()
                else:
                    content = summary_text[start_idx:next_idx].strip()
                
                if content:
                    return content

        return None

    def get_section_from_summary(self, summary_text: str, section_name: str) -> str:
        """Extract a specific section from the summary text"""
        sections = {
            'topics': ('Key Topics', 'Decisions & Actions'),
            'decisions': ('Decisions & Actions', 'Status & Questions'),
            'questions': ('Status & Questions', 'Contributors'),
            'contributors': ('Contributors', 'Needs Immediate Attention'),
            'urgent': ('Needs Immediate Attention', 'Summary Details')
        }

        if section_name not in sections:
            return None

        start_marker, end_marker = sections[section_name]
        try:
            start_idx = summary_text.index(start_marker)
            end_idx = summary_text.index(end_marker)
            section_text = summary_text[start_idx:end_idx].strip()
            
            # Remove the section header
            section_text = section_text.replace(start_marker, '').strip()
            
            # Keep only bullet points
            bullet_points = [line.strip() for line in section_text.split('\n') if line.strip().startswith('•')]
            return '\n'.join(bullet_points)
            
        except ValueError:
            return None

    def store_summary(self, channel_id: str, summary_text: str):
        """Store the last summary for a channel"""
        self.last_summaries[channel_id] = summary_text

    def get_last_summary(self, channel_id: str) -> str:
        """Get the last summary for a channel"""
        return self.last_summaries.get(channel_id)

    def set_current_focus(self, channel_id: str, focus_type: str):
        """Set the current focus type for follow-up questions"""
        self.current_focus[channel_id] = focus_type

    def get_current_focus(self, channel_id: str) -> str:
        """Get the current focus type for a channel"""
        return self.current_focus.get(channel_id) 