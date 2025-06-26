import logging
from typing import List, Dict, Optional
from ..models import ChannelCategory, MessageFilter

logger = logging.getLogger(__name__)

class BlockKitService:
    """Service for generating Slack Block Kit UI components"""

    @staticmethod
    def create_category_select_block(categories: List[Dict], action_id: str) -> Dict:
        """Create a dropdown for selecting categories"""
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Choose a category to summarize:"
            },
            "accessory": {
                "type": "static_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select a category",
                    "emoji": True
                },
                "options": [
                    {
                        "text": {
                            "type": "plain_text",
                            "text": category['name'],
                            "emoji": True
                        },
                        "value": str(category['id'])
                    } for category in categories
                ],
                "action_id": action_id
            }
        }

    @staticmethod
    def create_filter_select_block(filters: List[MessageFilter], action_id: str) -> Dict:
        """Create a dropdown for selecting filters"""
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Apply a message filter:"
            },
            "accessory": {
                "type": "static_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select a filter",
                    "emoji": True
                },
                "options": [
                    {
                        "text": {
                            "type": "plain_text",
                            "text": f"{f.name} ({f.match_type})",
                            "emoji": True
                        },
                        "value": str(f.id)
                    } for f in filters
                ],
                "action_id": action_id
            }
        }

    @staticmethod
    def create_summary_options_block() -> List[Dict]:
        """Create blocks for summary options"""
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Choose Summary Type:*"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Single Channel",
                            "emoji": True
                        },
                        "value": "single",
                        "action_id": "summary_type_single"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Category",
                            "emoji": True
                        },
                        "value": "category",
                        "action_id": "summary_type_category"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "All Channels",
                            "emoji": True
                        },
                        "value": "all",
                        "action_id": "summary_type_all"
                    }
                ]
            }
        ]

    @staticmethod
    def create_filter_creation_blocks() -> List[Dict]:
        """Create blocks for filter creation"""
        return [
            {
                "type": "input",
                "block_id": "filter_name",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "filter_name_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Enter filter name"
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "Filter Name"
                }
            },
            {
                "type": "section",
                "block_id": "match_type",
                "text": {
                    "type": "mrkdwn",
                    "text": "Match Type:"
                },
                "accessory": {
                    "type": "radio_buttons",
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Match All Conditions",
                                "emoji": True
                            },
                            "value": "all"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Match Any Condition",
                                "emoji": True
                            },
                            "value": "any"
                        }
                    ],
                    "action_id": "match_type_select"
                }
            }
        ]

    @staticmethod
    def create_category_management_blocks(categories: List[Dict]) -> List[Dict]:
        """Create blocks for category management"""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Channel Categories*"
                }
            }
        ]

        for category in categories:
            # Format channel names - just use the stored channel name
            channel_list = "\n".join([f"• #{ch['name']}" for ch in category['channels']])
            
            blocks.extend([
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{category['name']}*\n{channel_list or 'No channels yet'}"
                    },
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Manage",
                            "emoji": True
                        },
                        "value": str(category['id']),
                        "action_id": f"manage_category_{category['id']}"
                    }
                },
                {"type": "divider"}
            ])

        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Create New Category",
                        "emoji": True
                    },
                    "style": "primary",
                    "value": "create_new",
                    "action_id": "create_category"
                }
            ]
        })

        return blocks

    def create_category_modal(self) -> Dict:
        """Create a modal view for category creation"""
        return {
            "type": "modal",
            "callback_id": "create_category_modal",
            "title": {
                "type": "plain_text",
                "text": "Create Category",
                "emoji": True
            },
            "submit": {
                "type": "plain_text",
                "text": "Create",
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
                    "block_id": "category_name",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "category_name_input",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Enter category name"
                        }
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Name",
                        "emoji": True
                    }
                },
                {
                    "type": "input",
                    "block_id": "category_description",
                    "optional": True,
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "category_description_input",
                        "multiline": True,
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Enter category description"
                        }
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Description",
                        "emoji": True
                    }
                },
                {
                    "type": "input",
                    "block_id": "category_channels",
                    "element": {
                        "type": "multi_channels_select",
                        "action_id": "category_channels_input",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select channels",
                            "emoji": True
                        }
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Channels",
                        "emoji": True
                    }
                }
            ]
        }

    @staticmethod
    def create_loading_message() -> Dict:
        """Create a loading message block"""
        return {
            "response_type": "ephemeral",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": ":hourglass_flowing_sand: Processing your request..."
                    }
                }
            ]
        }

    @staticmethod
    def create_error_message(error_text: str) -> Dict:
        """Create an error message block"""
        return {
            "response_type": "ephemeral",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":x: Error: {error_text}"
                    }
                }
            ]
        } 