import re
from typing import List, Dict, Any

class SlackFormatter:
    """Utility class for formatting messages for Slack"""
    
    @staticmethod
    def format_code_block(text: str, language: str = None) -> str:
        """Format text as a code block"""
        if language:
            return f"```{language}\n{text}\n```"
        return f"```\n{text}\n```"
    
    @staticmethod
    def format_inline_code(text: str) -> str:
        """Format text as inline code"""
        return f"`{text}`"
    
    @staticmethod
    def format_bold(text: str) -> str:
        """Format text as bold"""
        return f"*{text}*"
    
    @staticmethod
    def format_italic(text: str) -> str:
        """Format text as italic"""
        return f"_{text}_"
    
    @staticmethod
    def format_link(url: str, text: str = None) -> str:
        """Format a URL as a link"""
        if text:
            return f"<{url}|{text}>"
        return f"<{url}>"
    
    @staticmethod
    def format_user_mention(user_id: str) -> str:
        """Format a user mention"""
        return f"<@{user_id}>"
    
    @staticmethod
    def format_channel_mention(channel_id: str) -> str:
        """Format a channel mention"""
        return f"<#{channel_id}>"
    
    @staticmethod
    def create_blocks(content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create Slack blocks for rich formatting"""
        return content
    
    @staticmethod
    def create_section_block(text: str, markdown: bool = True) -> Dict[str, Any]:
        """Create a section block"""
        text_type = "mrkdwn" if markdown else "plain_text"
        return {
            "type": "section",
            "text": {
                "type": text_type,
                "text": text
            }
        }
    
    @staticmethod
    def create_divider_block() -> Dict[str, Any]:
        """Create a divider block"""
        return {"type": "divider"}
    
    @staticmethod
    def create_button_block(text: str, action_id: str, value: str = None) -> Dict[str, Any]:
        """Create a button element"""
        button = {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": text
            },
            "action_id": action_id
        }
        if value:
            button["value"] = value
        return button
    
    @staticmethod
    def truncate_text(text: str, max_length: int = 3000) -> str:
        """Truncate text to fit Slack's message limits"""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."
    
    @staticmethod
    def escape_slack_markdown(text: str) -> str:
        """Escape Slack markdown characters"""
        # Escape special Slack markdown characters
        escape_chars = ['*', '_', '`', '~']
        for char in escape_chars:
            text = text.replace(char, f"\\{char}")
        return text 