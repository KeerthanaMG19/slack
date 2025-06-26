# 🚀 Complete Setup Guide

## ⚠️ IMPORTANT: API Key Configuration Required

This project requires you to obtain and configure your own API keys. **All placeholder keys must be replaced with actual working keys.**

## 📋 Prerequisites

- Python 3.13+
- Git
- A Slack workspace where you can install apps
- Google account for Gemini AI access

## 🔧 Step-by-Step Setup

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/ai-slack-bot.git
cd ai-slack-bot
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
```bash
# Copy the environment template
cp config/environment.example .env

# Edit the .env file with your actual API keys
nano .env  # or use your preferred editor
```

### 4. Obtain Required API Keys

#### 🔑 **Slack API Keys**

1. **Go to Slack API**: https://api.slack.com/apps
2. **Create New App**:
   - Click "Create New App"
   - Choose "From scratch"
   - Enter app name: "AI Summary Bot"
   - Select your workspace
3. **Configure OAuth & Permissions**:
   - Go to "OAuth & Permissions" in sidebar
   - Scroll to "Scopes" section
   - Add these **Bot Token Scopes**:
     - `channels:history` - Read messages
     - `channels:read` - View channel info
     - `users:read` - Get user information
     - `chat:write` - Send messages
     - `commands` - Receive slash commands
4. **Install App to Workspace**:
   - Click "Install to Workspace"
   - Authorize the app
   - **Copy the Bot User OAuth Token** (starts with `xoxb-`)
5. **Get Signing Secret**:
   - Go to "Basic Information" > "App Credentials"
   - **Copy the Signing Secret**
6. **Update .env file**:
   ```
   SLACK_BOT_TOKEN=xoxb-your-actual-token-here
   SLACK_SIGNING_SECRET=your-actual-signing-secret-here
   ```

#### 🤖 **Google Gemini AI Key**

1. **Go to Google AI Studio**: https://makersuite.google.com/app/apikey
2. **Create API Key**:
   - Click "Create API Key"
   - Choose existing project or create new one
   - **Copy the generated API key**
3. **Update .env file**:
   ```
   GEMINI_API_KEY=your-actual-gemini-api-key-here
   ```

#### 🔐 **Django Secret Key**

1. **Generate a secure key**:
   ```bash
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```
2. **Update .env file**:
   ```
   DJANGO_SECRET_KEY=your-generated-secret-key-here
   ```

### 5. Initialize Database
```bash
python manage.py migrate
```

### 6. Start the Development Server
```bash
./start_dev.sh
```

### 7. Configure Slack Slash Command

1. **Get your ngrok URL** from the terminal output (something like `https://abc123.ngrok-free.app`)
2. **Go back to your Slack app** at https://api.slack.com/apps
3. **Add Slash Command**:
   - Go to "Slash Commands" in sidebar
   - Click "Create New Command"
   - **Command**: `/summary`
   - **Request URL**: `https://secretly-pretty-swine.ngrok-free.app/slack/commands/ultra/`
   - **Short Description**: "Generate AI-powered channel summaries"
   - **Usage Hint**: `#channel-name or unread #channel-name`
4. **Save the command**

### 8. Test the Bot

1. **Go to your Slack workspace**
2. **Try these commands**:
   ```
   /summary #general
   /summary unread #general
   ```
3. **You should see**:
   - Immediate "Processing..." message
   - Followed by AI-generated summary

## ✅ Verification Checklist

- [ ] All API keys replaced in `.env` file
- [ ] No placeholder values remain (no `your-*-here` strings)
- [ ] Django server starts without errors
- [ ] ngrok tunnel is active
- [ ] Slack slash command configured
- [ ] Bot responds to `/summary` commands
- [ ] AI summaries are generated successfully

## 🚨 Common Issues

### "Invalid API Key" Errors
- **Slack**: Ensure token starts with `xoxb-` and has correct scopes
- **Gemini**: Verify API key is active and billing is enabled if required

### "Command not found" in Slack
- Check that Request URL in Slack app matches your ngrok URL exactly
- Ensure ngrok tunnel is running

### "Bot not in channel" Errors
- Invite the bot to channels: `/invite @YourBotName`
- Or use public channels where the bot has access

### Django Server Won't Start
- Check all environment variables are set
- Verify Python dependencies are installed
- Run `python manage.py check` for issues

## 🎯 Next Steps

Once everything is working:

1. **Customize the bot name** in your Slack app settings
2. **Add the bot to channels** you want to summarize
3. **Try both summary modes**:
   - Complete: `/summary #channel`
   - Unread: `/summary unread #channel`
4. **Monitor logs** for any issues
5. **Consider production deployment** (see DEPLOYMENT.md)

## 📞 Support

If you encounter issues:

1. Check the Django logs for detailed error messages
2. Verify all API keys are correctly configured
3. Test each API key individually
4. Open an issue with full error details

---

**Remember**: This bot requires active API keys to function. The placeholder values in the repository will not work and must be replaced with your actual credentials.