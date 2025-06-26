import logging
from typing import List, Dict, Optional
from django.core.cache import cache
from django.db import transaction
from ..models import ChannelCategory, CategoryChannel
from .slack_service import SlackService

logger = logging.getLogger(__name__)

class CategoryService:
    """Service for managing channel categories"""

    CACHE_TTL = 3600  # 1 hour cache

    def create_category(self, name: str, description: str, channels: List[str], created_by: str) -> ChannelCategory:
        """Create a new category with associated channels"""
        try:
            logger.info(f"[CATEGORY_CREATE] Starting category creation: name={name}, description={description}, channels={channels}")
            slack_client = SlackService().client
            
            with transaction.atomic():
                # Create the category
                category = ChannelCategory.objects.create(
                    name=name,
                    description=description,
                    created_by=created_by
                )
                logger.info(f"[CATEGORY_CREATE] Created category with ID: {category.id}")
                
                # Add channels to the category
                for channel_id in channels:
                    try:
                        # Get channel info from Slack
                        channel_info = slack_client.conversations_info(channel=channel_id)
                        if channel_info and channel_info['ok']:
                            channel_name = channel_info['channel']['name']
                            logger.info(f"[CATEGORY_CREATE] Got channel name from Slack: {channel_name}")
                            
                            CategoryChannel.objects.create(
                                category=category,
                                channel_id=channel_id,
                                channel_name=channel_name,
                                added_by=created_by
                            )
                            logger.info(f"[CATEGORY_CREATE] Added channel {channel_name} to category {category.id}")
                    except Exception as e:
                        logger.error(f"[CATEGORY_CREATE] Error getting channel info: {str(e)}", exc_info=True)
                        # If we can't get the name, store the ID as a fallback
                        CategoryChannel.objects.create(
                            category=category,
                            channel_id=channel_id,
                            channel_name=channel_id.lstrip('C'),
                            added_by=created_by
                        )
                
                logger.info(f"[CATEGORY_CREATE] Successfully created category {category.id} with {len(channels)} channels")
                return category
                
        except Exception as e:
            logger.error(f"[CATEGORY_CREATE] Error creating category: {str(e)}", exc_info=True)
            raise Exception(f"Failed to create category: {str(e)}")

    def add_channel_to_category(self, category_id: int, channel_id: str, channel_name: str, user_id: str) -> bool:
        """Add a channel to an existing category"""
        try:
            category = ChannelCategory.objects.get(id=category_id, created_by=user_id)
            CategoryChannel.objects.create(
                category=category,
                channel_id=channel_id,
                channel_name=channel_name.lstrip('#'),
                added_by=user_id
            )
            return True
        except Exception as e:
            logger.error(f"[CATEGORY_ADD_CHANNEL] Error adding channel to category {category_id}: {str(e)}", exc_info=True)
            return False

    def remove_channel_from_category(self, category_id: int, channel_id: str) -> bool:
        """Remove a channel from a category"""
        try:
            CategoryChannel.objects.filter(
                category_id=category_id,
                channel_id=channel_id
            ).delete()
            return True
        except Exception as e:
            logger.error(f"[CATEGORY_REMOVE_CHANNEL] Error removing channel from category {category_id}: {str(e)}", exc_info=True)
            return False

    def get_user_categories(self, user_id: str) -> List[Dict]:
        """Get all categories created by a user"""
        try:
            categories = []
            for category in ChannelCategory.objects.filter(created_by=user_id):
                channels = CategoryChannel.objects.filter(category=category)
                categories.append({
                    'id': category.id,
                    'name': category.name,
                    'description': category.description,
                    'channels': [{'id': ch.channel_id, 'name': ch.channel_name} for ch in channels]
                })
            return categories
        except Exception as e:
            logger.error(f"[CATEGORY_GET] Error getting categories for user {user_id}: {str(e)}", exc_info=True)
            return []

    def get_category_channels(self, category_id: int):
        """Get all channel IDs and names in a category"""
        return list(CategoryChannel.objects.filter(category_id=category_id).values_list('channel_id', flat=True))

    def get_channel_categories(self, channel_id: str) -> List[ChannelCategory]:
        """Get all categories that a channel belongs to"""
        return ChannelCategory.objects.filter(channels__channel_id=channel_id)

    def delete_category(self, category_id: int, user_id: str) -> bool:
        """Delete a category and its channel associations"""
        try:
            category = ChannelCategory.objects.get(id=category_id, created_by=user_id)
            category.delete()
            return True
        except ChannelCategory.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"[CATEGORY_DELETE] Error deleting category {category_id}: {str(e)}", exc_info=True)
            return False

    def rename_category(self, category_id: int, new_name: str, user_id: str) -> Optional[ChannelCategory]:
        """Rename a category"""
        try:
            category = ChannelCategory.objects.get(id=category_id, created_by=user_id)
            category.name = new_name
            category.save()
            self._invalidate_cache(user_id)
            return category
        except ChannelCategory.DoesNotExist:
            return None

    def _invalidate_cache(self, user_id: str):
        """Invalidate the cache for a user's categories"""
        cache_key = f"user_categories_{user_id}"
        cache.delete(cache_key)