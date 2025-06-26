# API Documentation

## Overview

The SlackOpsBot Slack Bot provides several HTTP endpoints for integration with Slack and system monitoring.

## Base URL

- **Development**: `http://localhost:8000`
- **Production**: `https://your-domain.com`

## Authentication

All Slack endpoints use Slack's signature verification for security. The bot validates:
- Request signatures using `SLACK_SIGNING_SECRET`
- OAuth tokens for API calls
- Request timestamps to prevent replay attacks

## Endpoints

### Health Check

#### `GET /health/`

Returns the current status of the application and its dependencies.

**Response:**
```json
{
    "status": "ok",
    "timestamp": "2025-06-23T02:02:20.213248",
    "django_debug": true,
    "environment_variables": {
        "SLACK_BOT_TOKEN": true,
        "SLACK_SIGNING_SECRET": true,
        "GEMINI_API_KEY": true,
        "DJANGO_SECRET_KEY": true
    }
}
```

**Status Codes:**
- `200 OK` - All systems operational
- `500 Internal Server Error` - System issues detected

---

### Slack Commands (Ultra-Fast)

#### `POST /slack/commands/ultra/`

**Recommended endpoint** for Slack slash commands with ultra-fast response times.

**Example Request URL:**  
`https://secretly-pretty-swine.ngrok-free.app/slack/commands/ultra/`

**Request Headers:**
```
Content-Type: application/x-www-form-urlencoded
X-Slack-Signature: v0=signature
X-Slack-Request-Timestamp: timestamp
```

**Request Parameters:**
```
command: /summary
text: channel-name
user_id: U1234567890
user_name: john.doe
channel_id: C1234567890
team_id: T1234567890
response_url: https://hooks.slack.com/commands/...
```

**Response (Immediate):**
```json
{
    "response_type": "ephemeral",
    "text": "⚡ **Processing summary for #general...**\n\n🤖 AI analysis starting now with full OAuth permissions.\n📊 Fetching messages and generating intelligent summary.\n⏱️ This usually takes 10-30 seconds for detailed analysis.\n\n✨ **Full AI-powered summary will appear shortly!**"
}
```

**Background Processing:**
After the immediate response, the system:
1. Validates channel access and permissions
2. Fetches recent messages (last 24 hours)
3. Enriches messages with user information
4. Generates AI summary using Google Gemini
5. Posts final summary using `response_url`

**Final Summary Format:**
```json
{
    "response_type": "in_channel",
    "text": "📊 **Summary for #general** (Last 24 Hours)\n\n🎯 **Key Topics:**\n• Topic 1\n• Topic 2\n\n👥 **Active Participants:** 5 users\n📈 **Activity:** 23 messages\n\n💡 **Key Insights:**\n• Insight 1\n• Insight 2",
    "replace_original": true
}
```

---

### Slack Commands (Standard)

#### `POST /slack/commands/`

Standard slash command endpoint with comprehensive processing and timeout protection.

**Same request/response format as ultra-fast endpoint**

**Features:**
- Built-in timeout protection (2.5s limit)
- Step-by-step processing logs
- Comprehensive error handling
- Fallback to quick summaries if processing is slow

---

### Slack Events

#### `POST /slack/events/`

Handles Slack Event API callbacks for real-time event processing.

**URL Verification Challenge:**
```json
{
    "type": "url_verification",
    "challenge": "challenge_string"
}
```

**Response:**
```json
{
    "challenge": "challenge_string"
}
```

**Event Callback:**
```json
{
    "type": "event_callback",
    "event": {
        "type": "message",
        "text": "Hello world",
        "user": "U1234567890",
        "channel": "C1234567890"
    }
}
```

---

### Test Configuration

#### `GET /slack/test/`

Returns current bot configuration and service status for debugging.

**Response:**
```json
{
    "status": "ok",
    "timestamp": "2025-06-23T02:02:20.213248",
    "services": {
        "slack_service": "operational",
        "gemini_service": "operational"
    },
    "endpoints": {
        "health": "http://localhost:8000/health/",
        "slack_commands": "http://localhost:8000/slack/commands/",
        "slack_events": "http://localhost:8000/slack/events/"
    }
}
```

## Error Handling

### Standard Error Response

```json
{
    "response_type": "ephemeral",
    "text": "❌ Sorry, there was an error processing your command.\n\nError details: Description of error...\nDuration: 150.2ms\n\nPlease try again in a few moments."
}
```

### Common Error Scenarios

1. **Channel Not Found**
   ```json
   {
       "response_type": "ephemeral",
       "text": "❌ I couldn't find the channel #nonexistent.\n\nPlease make sure:\n• The channel name is spelled correctly\n• The channel exists and is accessible\n• You have permission to view the channel"
   }
   ```

2. **Permission Denied**
   ```json
   {
       "response_type": "ephemeral",
       "text": "❌ I need to be added to #private-channel first.\n\nPlease type `/invite @SlackOpsBot` in #private-channel, then try the summary command again."
   }
   ```

3. **No Messages Found**
   ```json
   {
       "response_type": "ephemeral",
       "text": "📭 No messages found in #quiet-channel in the last 24 hours.\n\nThe channel appears to be quiet recently. Try again when there's more activity!"
   }
   ```

## Rate Limiting

- **Slack API**: Respects Slack's rate limits (1+ requests per second)
- **Gemini API**: Managed through service-level rate limiting
- **Request Processing**: Unlimited concurrent requests with background processing

## Performance Metrics

- **Ultra-Fast Endpoint**: ~26ms response time
- **Standard Endpoint**: ~100-300ms response time
- **Background Processing**: 10-30 seconds for full AI analysis
- **Memory Usage**: ~50-100MB per request during processing

## Security

### Request Validation
- Slack signature verification on all endpoints
- Timestamp validation to prevent replay attacks
- OAuth token validation for API calls

### Data Protection
- No persistent storage of message content
- Temporary processing only
- Environment variable protection

### Error Information
- Sensitive information filtered from error responses
- Request IDs for debugging without exposing data
- Comprehensive logging without data leakage

## Documentation

### **User Documentation**
- ✅ **README.md**: Comprehensive project overview
- ✅ **Quick start guides**: Easy setup instructions
- ✅ **Feature descriptions**: Clear functionality explanations
- ✅ **Usage examples**: Practical command demonstrations