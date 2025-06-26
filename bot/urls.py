from django.urls import path
from . import views

urlpatterns = [
    # Base endpoint
    path('', views.index, name='index'),
    
    # Slack Events API endpoint
    path('slack/events/', views.slack_events, name='slack_events'),
    
    # Slack Commands endpoints
    path('slack/commands/', views.slack_commands, name='slack_commands'),
    
    # Slack Interactive Components endpoint
    path('slack/actions/', views.handle_block_actions, name='slack_actions'),
    
    # Health check endpoint
    path('health/', views.health, name='health_check'),
    
    # Test endpoint
    path('slack/test/', views.slack_test, name='slack_test'),
] 