# core/admin.py (or wherever your model lives)
from django.contrib import admin
from .models import UserSummaryState


@admin.register(UserSummaryState)
class UserSummaryStateAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'channel_id', 'last_summary_ts', 'updated_at')
    search_fields = ('user_id', 'channel_id')
    list_filter = ('updated_at',)
