from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

# ...existing code...

def handle_view_submission(payload):
    callback_id = payload["view"]["callback_id"]
    if callback_id.startswith("add_channel_modal_"):
        # Extract category id from callback_id if needed
        category_id = callback_id.replace("add_channel_modal_", "")
        # Extract selected channels
        selected_channels = (
            payload["view"]["state"]["values"]
            .get("add_channel_select", {})
            .get("add_channel_select_input", {})
            .get("selected_channels", [])
        )
        # TODO: Save or process the selected channels for the category
        print(f"[VIEW_SUBMISSION] Add channels {selected_channels} to category {category_id}")
        # Respond to Slack to close the modal
        return JsonResponse({"response_action": "clear"})
    # ...existing code...

@csrf_exempt
def slack_actions(request):
    # ...existing code...
    if payload_type == "view_submission":
        return handle_view_submission(payload)
    # ...existing code...