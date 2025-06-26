from django.db import models
from django.utils import timezone


class UserSummaryState(models.Model):
    """Track the last summary timestamp for each user-channel pair"""
    user_id = models.CharField(max_length=50)
    channel_id = models.CharField(max_length=50)
    last_summary_ts = models.CharField(max_length=50)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user_id', 'channel_id')

    @classmethod
    def get_last_summary_ts(cls, user_id, channel_id):
        """Get the last summary timestamp for a user-channel pair"""
        try:
            state = cls.objects.get(user_id=user_id, channel_id=channel_id)
            return state.last_summary_ts
        except cls.DoesNotExist:
            return "0"  # Return earliest possible timestamp

    @classmethod
    def update_last_summary_ts(cls, user_id, channel_id, new_ts):
        """Update the last summary timestamp for a user-channel pair"""
        cls.objects.update_or_create(
            user_id=user_id,
            channel_id=channel_id,
            defaults={'last_summary_ts': new_ts}
        )

class Feedback(models.Model):
    """Store user feedback about summaries"""
    user_id = models.CharField(max_length=50)
    channel_id = models.CharField(max_length=50)
    feedback = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)  # Keep the original field name

    def __str__(self):
        return f"Feedback from {self.user_id} in {self.channel_id}"

class ChannelCategory(models.Model):
    """Group channels into categories for organized summaries"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_by = models.CharField(max_length=50)  # Slack user ID
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Channel Categories"

    def __str__(self):
        return self.name

class CategoryChannel(models.Model):
    """Associate channels with categories (Many-to-Many relationship)"""
    category = models.ForeignKey(ChannelCategory, on_delete=models.CASCADE, related_name='channels')
    channel_id = models.CharField(max_length=50)
    channel_name = models.CharField(max_length=100)
    added_by = models.CharField(max_length=50)  # Slack user ID
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('category', 'channel_id')

    def __str__(self):
        return f"{self.category.name} - #{self.channel_name}"

class MessageFilter(models.Model):
    """Store user-defined message filters"""
    name = models.CharField(max_length=100)
    created_by = models.CharField(max_length=50)  # Slack user ID
    match_type = models.CharField(
        max_length=10,
        choices=[('all', 'Match All'), ('any', 'Match Any')],
        default='all'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.match_type})"

class FilterCondition(models.Model):
    """Individual conditions for message filters"""
    filter = models.ForeignKey(MessageFilter, on_delete=models.CASCADE, related_name='conditions')
    field = models.CharField(
        max_length=20,
        choices=[
            ('user', 'User'),
            ('keyword', 'Keyword'),
            ('reaction', 'Reaction'),
            ('time_range', 'Time Range'),
            ('has_thread', 'Has Thread'),
            ('has_files', 'Has Files'),
        ]
    )
    operator = models.CharField(
        max_length=20,
        choices=[
            ('equals', 'Equals'),
            ('contains', 'Contains'),
            ('starts_with', 'Starts With'),
            ('ends_with', 'Ends With'),
            ('greater_than', 'Greater Than'),
            ('less_than', 'Less Than'),
            ('is_true', 'Is True'),
            ('is_false', 'Is False'),
        ]
    )
    value = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.field} {self.operator} {self.value}"