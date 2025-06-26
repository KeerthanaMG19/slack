import json
import logging
from django.http import HttpResponse
from .conversation_handler import ConversationHandler
from ..services.slack_service import SlackService
from ..services.gemini_service import GeminiService

logger = logging.getLogger(__name__)

# Initialize services
slack_service = SlackService()
gemini_service = GeminiService()
conversation_handler = ConversationHandler(slack_service, gemini_service)

def slack_events_handler(request):
    """Handle incoming Slack events"""
    try:
        # Parse the event payload
        body = json.loads(request.body)
        logger.info(f"Received Slack event: {json.dumps(body, indent=2)}")
        
        # Handle URL verification
        if body.get('type') == 'url_verification':
            logger.info("Handling URL verification challenge")
            return HttpResponse(body.get('challenge'))

        # Extract event data
        event = body.get('event', {})
        event_type = event.get('type')
        logger.info(f"Processing event type: {event_type}")

        # Only process message events that aren't from the bot itself
        if event_type == 'message' and not event.get('bot_id'):
            try:
                logger.info(f"Processing message: {event.get('text', '')}")
                # Handle the message
                response = conversation_handler.handle_message(event)
                
                if response:
                    logger.info(f"Sending response: {response}")
                    # Send response back to Slack
                    slack_service.send_message(
                        channel=event.get('channel'),
                        text=response,
                        thread_ts=event.get('thread_ts')
                    )
                else:
                    logger.info("No response generated")
                
            except Exception as e:
                logger.error(f"Error handling Slack event: {str(e)}", exc_info=True)
                # Send error message to Slack
                slack_service.send_message(
                    channel=event.get('channel'),
                    text=":warning: Sorry, I encountered an error. Please try again!",
                    thread_ts=event.get('thread_ts')
                )

        return HttpResponse()

    except Exception as e:
        logger.error(f"Error processing Slack event: {str(e)}", exc_info=True)
        return HttpResponse(status=500)
