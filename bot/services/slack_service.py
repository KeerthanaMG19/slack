import logging
import time
import ssl
import certifi
from decimal import Decimal
from datetime import datetime, timedelta
from slack_sdk.web import WebClient 
from slack_sdk.errors import SlackApiError
from django.conf import settings
from django.core.cache import cache
from django.utils.timezone import now
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

class SlackService:
    """Service class for interacting with Slack API with SSL certificate handling"""

    RATE_LIMIT_DELAY = 0.5

    def __init__(self):
        """Initialize the Slack client with SSL context"""
        ssl_context = ssl.create_default_context(cafile=certifi.where())

        if settings.DEBUG:
            logger.warning("DEBUG mode: Using relaxed SSL verification for Slack API")
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        self.client = WebClient(token=settings.SLACK_BOT_TOKEN, ssl=ssl_context)
        self.bot_user_id = None
        logger.info("SlackService initialized with SSL context")

    def get_bot_user_id(self):
        """Get the Slack bot's user ID, cache it after first lookup"""
        if self.bot_user_id:
            return self.bot_user_id

        try:
            response = self.client.auth_test()
            self.bot_user_id = response['user_id']
            logger.info(f"Bot user ID: {self.bot_user_id}")
            return self.bot_user_id
        except SlackApiError as e:
            logger.error(f"SlackApiError getting bot user ID: {e.response['error']}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting bot user ID: {str(e)}", exc_info=True)
            return None

    def find_channel_id(self, channel_name):
        """Find the Slack channel ID by its name, using cache if possible"""
        clean_name = channel_name.strip().lstrip('#').lower()
        if not clean_name:
            logger.warning("Empty channel name provided")
            return None

        cache_key = f"channel_id_{clean_name}"
        cached_id = cache.get(cache_key)
        if cached_id:
            logger.info(f"Found cached channel ID for #{clean_name}: {cached_id}")
            return cached_id

        try:
            cursor = None
            while True:
                response = self.client.conversations_list(cursor=cursor, limit=200, types="public_channel,private_channel")
                for channel in response.get('channels', []):
                    if channel['name'].lower() == clean_name:
                        channel_id = channel['id']
                        cache.set(cache_key, channel_id, 3600)
                        return channel_id

                cursor = response.get('response_metadata', {}).get('next_cursor')
                if not cursor:
                    break
                time.sleep(self.RATE_LIMIT_DELAY)
        except SlackApiError as e:
            logger.error(f"SlackApiError finding channel #{clean_name}: {e.response['error']}")
        except Exception as e:
            logger.error(f"Unexpected error finding channel #{clean_name}: {str(e)}", exc_info=True)
        return None

    def check_bot_membership(self, channel_id):
        """Check if the bot is a member of a given Slack channel"""
        try:
            bot_user_id = self.get_bot_user_id()
            if not bot_user_id:
                return False

            response = self.client.conversations_members(channel=channel_id)
            return bot_user_id in response.get('members', [])
        except SlackApiError as e:
            return False
        except Exception as e:
            logger.error(f"Unexpected error checking bot membership in {channel_id}: {str(e)}", exc_info=True)
            return False

    def fetch_channel_messages(self, channel_id, hours_back=24):
        """Fetch messages from a channel within a given time window"""
        try:
            oldest_ts = (now() - timedelta(hours=hours_back)).timestamp()
            messages, cursor = [], None

            while True:
                response = self.client.conversations_history(channel=channel_id, oldest=str(oldest_ts), cursor=cursor, limit=200)
                messages += [msg for msg in response.get('messages', []) if self._is_valid_standard_message(msg)]
                cursor = response.get('response_metadata', {}).get('next_cursor')
                if not cursor:
                    break
                time.sleep(self.RATE_LIMIT_DELAY)

            return sorted(messages, key=lambda x: float(x['ts']))
        except Exception as e:
            logger.error(f"Error fetching messages: {str(e)}", exc_info=True)
            return []

    def enrich_messages_with_usernames(self, messages):
        """Replace user IDs with usernames in message list"""
        user_cache, enriched = {}, []
        for msg in messages:
            user_id = msg.get('user')
            if not user_id:
                continue

            if user_id not in user_cache:
                try:
                    user_info = self.get_user_info(user_id)
                    username = user_info.get('display_name') or user_info.get('real_name') or user_info.get('name', f'User_{user_id}')
                    user_cache[user_id] = username
                    time.sleep(0.1)
                except Exception as e:
                    user_cache[user_id] = f'User_{user_id}'

            enriched.append({
                'timestamp': datetime.fromtimestamp(float(msg['ts'])),
                'username': user_cache[user_id],
                'text': msg.get('text', ''),
                'user_id': user_id,
                'ts': msg['ts']
            })
        return enriched

    def fetch_unread_messages(self, channel_id, user_id):
        """Fetch unread messages for a user since their last summary timestamp"""
        try:
            from ..models import UserSummaryState
            last_ts = UserSummaryState.get_last_summary_ts(user_id, channel_id)
            logger.info(f"[Fetch Unread] Last summary TS for user {user_id} in {channel_id}: {last_ts}")
            messages, cursor, newest_ts = [], None, None

            while True:
                response = self.client.conversations_history(channel=channel_id, oldest=str(last_ts), cursor=cursor, limit=200)
                for msg in response.get('messages', []):
                    if Decimal(msg['ts']) <= Decimal(last_ts):
                        continue
                    if self._is_valid_unread_message(msg, user_id):
                        messages.append(msg)
                        if newest_ts is None or Decimal(msg['ts']) > Decimal(newest_ts):
                            newest_ts = msg['ts']
                cursor = response.get('response_metadata', {}).get('next_cursor')
                if not cursor:
                    break
                time.sleep(self.RATE_LIMIT_DELAY)

            logger.info(f"[Fetch Unread] Total valid messages: {len(messages)}, Newest TS: {newest_ts}")
            if newest_ts and messages:
                logger.info(f"[Update Summary] Saving summary for user={user_id}, channel={channel_id}, ts={newest_ts}")
                UserSummaryState.update_last_summary_ts(user_id, channel_id, newest_ts)
            return sorted(messages, key=lambda x: float(x['ts']))
        except Exception as e:
            logger.error(f"Error fetching unread messages: {str(e)}", exc_info=True)
            return []

    def _is_valid_unread_message(self, msg, user_id):
        """Validate if a message is unread and relevant to the user"""
        return (
            msg.get('type') == 'message' and
            not msg.get('bot_id') and
            msg.get('user') and
            msg.get('user') != user_id and
            not msg.get('subtype') and
            datetime.fromtimestamp(float(msg['ts'])) >= (now() - timedelta(hours=24))
        )

    def _is_valid_standard_message(self, msg):
        """Validate if a message is a regular user message (not bot/system)"""
        return (
            msg.get('type') == 'message' and
            not msg.get('bot_id') and
            msg.get('user') and
            not msg.get('subtype')
        )

    def send_message(self, channel: str, text: str, thread_ts: Optional[str] = None) -> bool:
        """Send a message to a Slack channel"""
        try:
            kwargs = {
                'channel': channel,
                'text': text
            }
            if thread_ts:
                kwargs['thread_ts'] = thread_ts

            response = self.client.chat_postMessage(**kwargs)
            return response['ok']
        except SlackApiError as e:
            logger.error(f"Error sending message: {str(e)}")
            return False

    def update_message(self, channel, ts, text, blocks=None):
        """Update an existing Slack message in a channel"""
        try:
            return self.client.chat_update(channel=channel, ts=ts, text=text, blocks=blocks)
        except Exception as e:
            logger.error(f"Error updating message: {str(e)}", exc_info=True)
            raise

    def get_user_info(self, user_id):
        """Get user profile info from Slack"""
        try:
            return self.client.users_info(user=user_id)['user']['profile']
        except Exception as e:
            logger.error(f"Error getting user info for {user_id}: {str(e)}", exc_info=True)
            raise

    def get_channel_info(self, channel_id):
        """Get channel information from Slack API"""
        try:
            logger.debug(f"Fetching channel info for {channel_id}")
            response = self.client.conversations_info(channel=channel_id)
            channel_info = response['channel']
            logger.debug(f"Channel info retrieved for {channel_id}")
            return channel_info
        except SlackApiError as e:
            logger.error(f"SlackApiError getting channel info for {channel_id}: {e.response['error']}")
            # Fallback: return dict with id as name
            return {'id': channel_id, 'name': channel_id}
        except Exception as e:
            logger.error(f"Unexpected error getting channel info for {channel_id}: {str(e)}", exc_info=True)
            return {'id': channel_id, 'name': channel_id}
    
    def fetch_unread_messages(self, channel_id, user_id):
        """Fetch only unread messages for a specific user in a channel"""
        try:
            logger.info(f"Fetching unread messages for user {user_id} in channel {channel_id}")
            
            from ..models import UserSummaryState
            
            # Step 1: Get the user's last summary timestamp from the database
            last_read_ts = UserSummaryState.get_last_summary_ts(user_id, channel_id)
            logger.info(f"User's last summary timestamp: {last_read_ts}")
            
            # Step 2: Check if user is a member of the channel
            try:
                members_response = self.client.conversations_members(channel=channel_id)
                if user_id not in members_response.get('members', []):
                    logger.warning(f"User {user_id} is not a member of channel {channel_id}")
                    return []
            except SlackApiError as e:
                if e.response['error'] == 'not_in_channel':
                    logger.warning(f"Bot not in channel {channel_id}")
                    return []
                logger.error(f"Error checking channel membership: {e.response['error']}")
                return []
            
            # Step 3: Fetch unread messages since the last summary
            logger.info(f"Fetching messages newer than {last_read_ts}")
            messages = []
            cursor = None
            page_count = 0
            newest_ts = None
            
            while True:
                page_count += 1
                logger.debug(f"Fetching unread messages page {page_count}")
                
                response = self.client.conversations_history(
                    channel=channel_id,
                    oldest=str(last_read_ts),
                    cursor=cursor,
                    limit=200
                )
                
                channel_messages = response.get('messages', [])
                logger.debug(f"Retrieved {len(channel_messages)} raw messages on page {page_count}")
                
                if not channel_messages:
                    break
                
                filtered_count = 0
                for msg in channel_messages:
                    if float(msg['ts']) <= float(last_read_ts):
                        continue
                    if self._is_valid_unread_message(msg, user_id):
                        messages.append(msg)
                        filtered_count += 1
                        if newest_ts is None or float(msg['ts']) > float(newest_ts):
                            newest_ts = msg['ts']
                
                logger.debug(f"Filtered to {filtered_count} unread messages on page {page_count}")
                
                cursor = response.get('response_metadata', {}).get('next_cursor')
                if not cursor:
                    break
                time.sleep(0.5)
            
            # Step 4: Update the user's summary timestamp
            if newest_ts and messages:
                UserSummaryState.update_last_summary_ts(user_id, channel_id, newest_ts)
                logger.info(f"Updated summary timestamp to {newest_ts} for user {user_id}")
            
            messages.sort(key=lambda x: float(x['ts']))
            logger.info(f"Found {len(messages)} truly unread messages for user {user_id} in {channel_id}")
            return messages

        except SlackApiError as e:
            logger.error(f"SlackApiError fetching unread messages from {channel_id}: {e.response['error']}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching unread messages from {channel_id}: {str(e)}", exc_info=True)
            return []
    
    def _is_valid_unread_message(self, msg, user_id):
        """Determine if a message is a valid unread message"""
        # Basic message validation
        if (msg.get('type') != 'message' or 
            msg.get('bot_id') or 
            not msg.get('user') or
            msg.get('subtype')):
            return False
        
        # Don't include the user's own messages
        if msg.get('user') == user_id:
            return False
        
        # Don't include very old messages (safety check - older than 24 hours)
        msg_time = datetime.fromtimestamp(float(msg['ts']))
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        if msg_time < cutoff_time:
            return False
        
        return True 

    def fetch_read_messages(self, channel_id, user_id):
        """Fetch all user messages from the channel from the past 24 hours (including read ones)"""
        try:
            logger.info(f"Fetching recent messages (read) for user {user_id} in channel {channel_id}")

            # Step 1: Fetch recent messages from the last 24 hours
            messages = self.fetch_channel_messages(channel_id, hours_back=24)

            # Step 2: Filter out user's own messages and non-standard ones
            filtered_messages = [
                msg for msg in messages
                if self._is_valid_read_message(msg, user_id)
            ]

            logger.info(f"Found {len(filtered_messages)} recent read messages for summarization")
            return filtered_messages
        except Exception as e:
            logger.error(f"Error fetching read messages: {str(e)}", exc_info=True)
            return []

    def _is_valid_read_message(self, msg, user_id):
        """Basic check for read messages (exclude user's own and bot messages)"""
        return (
            msg.get('type') == 'message' and
            not msg.get('bot_id') and
            msg.get('user') and
            msg.get('user') != user_id and
            not msg.get('subtype')
        )

    def fetch_thread_messages(self, channel_id: str, thread_ts: str) -> list:
        """Fetch all messages in a thread"""
        try:
            messages = []
            cursor = None
            
            while True:
                response = self.client.conversations_replies(
                    channel=channel_id,
                    ts=thread_ts,
                    cursor=cursor,
                    limit=200
                )
                
                thread_messages = response.get('messages', [])
                messages.extend([
                    msg for msg in thread_messages
                    if self._is_valid_standard_message(msg)
                ])
                
                cursor = response.get('response_metadata', {}).get('next_cursor')
                if not cursor:
                    break
                    
                time.sleep(self.RATE_LIMIT_DELAY)
            
            return sorted(messages, key=lambda x: float(x['ts']))
        except Exception as e:
            logger.error(f"Error fetching thread messages: {str(e)}", exc_info=True)
            return []

    def find_latest_thread(self, channel_id: str) -> Optional[dict]:
        """Find the most recent thread in a channel"""
        try:
            messages = self.fetch_channel_messages(channel_id, hours_back=24)
            
            # Filter for messages that have thread_ts (thread parent messages)
            thread_messages = [
                msg for msg in messages
                if msg.get('thread_ts') and msg.get('thread_ts') == msg.get('ts')  # Parent message check
            ]
            
            if thread_messages:
                latest_thread = max(thread_messages, key=lambda x: float(x['ts']))
                return {
                    'thread_ts': latest_thread['ts'],
                    'text': latest_thread.get('text', ''),
                    'user': latest_thread.get('user')
                }
            
            return None
        except Exception as e:
            logger.error(f"Error finding latest thread: {str(e)}", exc_info=True)
            return None

    def find_thread_by_topic(self, channel_id: str, topic: str, hours_back: int = 24) -> Optional[dict]:
        """Find a thread that matches the given topic"""
        try:
            messages = self.fetch_channel_messages(channel_id, hours_back=hours_back)
            
            # Filter for thread parent messages
            thread_messages = [
                msg for msg in messages
                if msg.get('thread_ts') and msg.get('thread_ts') == msg.get('ts')
            ]
            
            # Find best matching thread based on topic
            best_match = None
            highest_similarity = 0
            
            for msg in thread_messages:
                # Simple word matching for now - could be enhanced with better NLP
                msg_text = msg.get('text', '').lower()
                topic_words = set(topic.lower().split())
                
                # Calculate similarity based on word overlap
                matching_words = sum(1 for word in topic_words if word in msg_text)
                similarity = matching_words / len(topic_words) if topic_words else 0
                
                if similarity > highest_similarity:
                    highest_similarity = similarity
                    best_match = msg
            
            if best_match and highest_similarity > 0.3:  # Threshold for minimum similarity
                return {
                    'thread_ts': best_match['ts'],
                    'text': best_match.get('text', ''),
                    'user': best_match.get('user'),
                    'similarity': highest_similarity
                }
            
            return None
        except Exception as e:
            logger.error(f"Error finding thread by topic: {str(e)}", exc_info=True)
            return None

    def get_channel_messages(self, channel_id: str, channel_name: str = None) -> Optional[List[Dict]]:
        """Get messages from a channel"""
        try:
            # Get channel history
            response = self.client.conversations_history(
                channel=channel_id,
                limit=100  # Adjust as needed
            )
            
            if response['ok']:
                return response['messages']
            return None
            
        except SlackApiError as e:
            logger.error(f"SlackApiError finding channel #{channel_name}: {str(e)}")
            return None

    def get_thread_messages(self, channel_id: str, thread_ts: str) -> Optional[List[Dict]]:
        """Get messages from a thread"""
        try:
            response = self.client.conversations_replies(
                channel=channel_id,
                ts=thread_ts
            )
            
            if response['ok']:
                return response['messages']
            return None
            
        except SlackApiError as e:
            logger.error(f"Error getting thread messages: {str(e)}")
            return None

    def list_bot_channels(self) -> List[Dict]:
        """List all channels that the bot is a member of"""
        try:
            channels = []
            cursor = None
            
            while True:
                response = self.client.conversations_list(
                    types='public_channel,private_channel',
                    exclude_archived=True,
                    cursor=cursor,
                    limit=200
                )
                
                if not response.get('ok'):
                    logger.error(f"Error listing channels: {response.get('error')}")
                    break
                
                for channel in response.get('channels', []):
                    if channel.get('is_member'):
                        channels.append({
                            'id': channel['id'],
                            'name': channel['name'],
                            'is_private': channel.get('is_private', False)
                        })
                
                cursor = response.get('response_metadata', {}).get('next_cursor')
                if not cursor:
                    break
                time.sleep(self.RATE_LIMIT_DELAY)
            
            return channels
            
        except Exception as e:
            logger.error(f"Error listing bot channels: {str(e)}")
            return []

    def fetch_channel_messages(self, channel_id: str, hours_back: int = 24, oldest_ts: Optional[str] = None) -> List[Dict]:
        """Fetch messages from a channel, either by hours back or since a specific timestamp"""
        try:
            if oldest_ts is None:
                from datetime import datetime, timedelta
                oldest_ts = str((datetime.now() - timedelta(hours=hours_back)).timestamp())

            messages = []
            cursor = None

            while True:
                response = self.client.conversations_history(
                    channel=channel_id,
                    oldest=oldest_ts,
                    cursor=cursor,
                    limit=200
                )

                if not response.get('ok'):
                    logger.error(f"Error fetching messages: {response.get('error')}")
                    break

                messages.extend(response.get('messages', []))
                cursor = response.get('response_metadata', {}).get('next_cursor')
                if not cursor:
                    break
                time.sleep(self.RATE_LIMIT_DELAY)

            return sorted(messages, key=lambda x: float(x['ts']))

        except Exception as e:
            logger.error(f"Error fetching channel messages: {str(e)}")
            return []



