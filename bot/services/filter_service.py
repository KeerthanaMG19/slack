import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from decimal import Decimal
from ..models import MessageFilter, FilterCondition

logger = logging.getLogger(__name__)

class FilterService:
    """Service for filtering Slack messages based on various criteria"""

    def __init__(self):
        self.operators = {
            'equals': lambda x, y: x == y,
            'contains': lambda x, y: y.lower() in x.lower(),
            'starts_with': lambda x, y: x.lower().startswith(y.lower()),
            'ends_with': lambda x, y: x.lower().endswith(y.lower()),
            'greater_than': lambda x, y: Decimal(x) > Decimal(y),
            'less_than': lambda x, y: Decimal(x) < Decimal(y),
            'is_true': lambda x, _: bool(x),
            'is_false': lambda x, _: not bool(x),
        }

    def apply_filter(self, messages: List[Dict], filter_id: int) -> List[Dict]:
        """Apply a saved filter to a list of messages"""
        try:
            message_filter = MessageFilter.objects.get(id=filter_id)
            conditions = FilterCondition.objects.filter(filter=message_filter)
            
            if not conditions.exists():
                return messages

            filtered_messages = []
            for message in messages:
                if message_filter.match_type == 'all':
                    if all(self._check_condition(message, condition) for condition in conditions):
                        filtered_messages.append(message)
                else:  # match_type == 'any'
                    if any(self._check_condition(message, condition) for condition in conditions):
                        filtered_messages.append(message)

            return filtered_messages

        except MessageFilter.DoesNotExist:
            logger.error(f"Filter with ID {filter_id} not found")
            return messages
        except Exception as e:
            logger.error(f"Error applying filter: {str(e)}")
            return messages

    def _check_condition(self, message: Dict, condition: FilterCondition) -> bool:
        """Check if a message matches a single filter condition"""
        try:
            if condition.field == 'user':
                return self._apply_operator(
                    message.get('username', ''),
                    condition.operator,
                    condition.value
                )
            
            elif condition.field == 'keyword':
                return self._apply_operator(
                    message.get('text', ''),
                    condition.operator,
                    condition.value
                )
            
            elif condition.field == 'reaction':
                reactions = [r['name'] for r in message.get('reactions', [])]
                return any(
                    self._apply_operator(reaction, condition.operator, condition.value)
                    for reaction in reactions
                )
            
            elif condition.field == 'time_range':
                msg_time = datetime.fromtimestamp(float(message.get('ts', 0)))
                hours = int(condition.value)
                cutoff = datetime.now() - timedelta(hours=hours)
                return msg_time > cutoff if condition.operator == 'greater_than' else msg_time < cutoff
            
            elif condition.field == 'has_thread':
                has_thread = 'thread_ts' in message or 'parent_user_id' in message
                return has_thread if condition.value.lower() == 'true' else not has_thread
            
            elif condition.field == 'has_files':
                has_files = bool(message.get('files', []))
                return has_files if condition.value.lower() == 'true' else not has_files
            
            return False

        except Exception as e:
            logger.error(f"Error checking condition: {str(e)}")
            return False

    def _apply_operator(self, value: Any, operator: str, target: str) -> bool:
        """Apply an operator to compare two values"""
        try:
            op_func = self.operators.get(operator)
            if op_func:
                return op_func(str(value), str(target))
            return False
        except Exception as e:
            logger.error(f"Error applying operator: {str(e)}")
            return False

    def create_filter(self, name: str, created_by: str, match_type: str = 'all') -> MessageFilter:
        """Create a new message filter"""
        return MessageFilter.objects.create(
            name=name,
            created_by=created_by,
            match_type=match_type
        )

    def add_condition(self, filter_id: int, field: str, operator: str, value: str) -> FilterCondition:
        """Add a condition to an existing filter"""
        message_filter = MessageFilter.objects.get(id=filter_id)
        return FilterCondition.objects.create(
            filter=message_filter,
            field=field,
            operator=operator,
            value=value
        )

    def get_user_filters(self, user_id: str) -> List[MessageFilter]:
        """Get all filters created by a user"""
        return MessageFilter.objects.filter(created_by=user_id) 