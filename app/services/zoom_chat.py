# ============================================================
# app/services/zoom_chat.py
# ============================================================

import os
import json
import requests

from dotenv import load_dotenv

from app.services.zoom_auth import (
    get_zoom_access_token,
    refresh_zoom_access_token,
)

load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================

ZOOM_API_BASE = "https://api.zoom.us/v2"


# ============================================================
# ENVIRONMENT HELPER
# ============================================================

def get_env(
    name: str,
    default: str | None = None,
):
    value = os.getenv(name)

    if value is None:
        return default

    value = value.strip()

    if not value:
        return default

    return value


# ============================================================
# AUTHENTICATED ZOOM REQUEST
# ============================================================

def zoom_chat_request(
    method: str,
    url: str,
    **kwargs,
):
    """
    Make authenticated request to Zoom.

    Automatically refreshes OAuth token on HTTP 401.
    """

    access_token = get_zoom_access_token()

    if not access_token:
        return None, {
            "success": False,
            "status_code": 401,
            "error": "ZOOM_ACCESS_TOKEN is not configured.",
        }

    headers = kwargs.pop("headers", {})

    headers["Authorization"] = (
        f"Bearer {access_token}"
    )

    headers.setdefault(
        "Content-Type",
        "application/json",
    )

    headers.setdefault(
        "Accept",
        "application/json",
    )

    # ========================================================
    # FIRST REQUEST
    # ========================================================

    try:

        response = requests.request(
            method,
            url,
            headers=headers,
            timeout=60,
            **kwargs,
        )

    except requests.RequestException as e:

        return None, {
            "success": False,
            "status_code": 500,
            "error": "Unable to connect to Zoom.",
            "details": str(e),
        }

    # ========================================================
    # TOKEN EXPIRED
    # ========================================================

    if response.status_code == 401:

        print("[ZOOM CHAT] Access token expired.")
        print("[ZOOM CHAT] Refreshing token...")

        refresh_result = refresh_zoom_access_token()

        if not refresh_result.get("success"):

            return None, {
                "success": False,
                "status_code": 401,
                "error": (
                    "Zoom access token expired "
                    "and refresh failed."
                ),
                "details": refresh_result,
            }

        new_access_token = (
            refresh_result.get("access_token")
        )

        if not new_access_token:

            return None, {
                "success": False,
                "status_code": 401,
                "error": (
                    "Token refresh succeeded "
                    "but no access token was returned."
                ),
            }

        headers["Authorization"] = (
            f"Bearer {new_access_token}"
        )

        # ====================================================
        # RETRY
        # ====================================================

        try:

            response = requests.request(
                method,
                url,
                headers=headers,
                timeout=60,
                **kwargs,
            )

        except requests.RequestException as e:

            return None, {
                "success": False,
                "status_code": 500,
                "error": (
                    "Zoom request failed after "
                    "token refresh."
                ),
                "details": str(e),
            }

    return response, None


# ============================================================
# CREATE ZOOM TEAM CHAT CHANNEL
# ============================================================

def create_zoom_channel(
    channel_name: str,
    channel_type: int = 3,
):
    """
    Create a Zoom Team Chat channel.

    Zoom endpoint:

        POST /chat/users/me/channels

    Zoom channel types:

        1 = Private channel
        2 = Private channel for same Zoom account
        3 = Public channel
        4 = Group chat

    Default:

        3 = Public channel
    """

    # ========================================================
    # VALIDATION
    # ========================================================

    if not channel_name:

        return {
            "success": False,
            "status_code": 400,
            "error": "Channel name cannot be empty.",
        }

    channel_name = channel_name.strip()

    if not channel_name:

        return {
            "success": False,
            "status_code": 400,
            "error": "Channel name cannot be empty.",
        }

    if len(channel_name) > 128:

        return {
            "success": False,
            "status_code": 400,
            "error": "Channel name is too long.",
        }

    # ========================================================
    # VALIDATE TYPE
    # ========================================================

    if channel_type not in {1, 2, 3, 4}:

        return {
            "success": False,
            "status_code": 400,
            "error": (
                "Invalid channel type. "
                "Allowed values are 1, 2, 3, or 4."
            ),
        }

    # ========================================================
    # URL
    # ========================================================

    url = (
        f"{ZOOM_API_BASE}"
        "/chat/users/me/channels"
    )

    # ========================================================
    # CORRECT ZOOM PAYLOAD
    # ========================================================
    #
    # IMPORTANT:
    #
    # name and type are TOP LEVEL fields.
    #
    # They must NOT be placed inside
    # channel_settings.
    #
    # ========================================================

    payload = {
        "name": channel_name,
        "type": channel_type,
        "channel_settings": {
            "add_member_permissions": 1,
            "new_members_can_see_previous_messages_files": True,
            "posting_permissions": 1,
            "mention_all_permissions": 1,
        },
    }

    print(
        "[ZOOM CHAT] Creating channel..."
    )

    print(
        "[ZOOM CHAT] Channel name:",
        channel_name,
    )

    print(
        "[ZOOM CHAT] Channel type:",
        channel_type,
    )

    print(
        "[ZOOM CHAT] Payload:",
        json.dumps(
            payload,
            indent=2,
        ),
    )

    # ========================================================
    # REQUEST
    # ========================================================

    response, error = zoom_chat_request(
        "POST",
        url,
        json=payload,
    )

    if error:
        return error

    # ========================================================
    # RESPONSE
    # ========================================================

    try:

        data = response.json()

    except ValueError:

        data = {
            "raw_response": response.text
        }

    # ========================================================
    # ERROR
    # ========================================================

    if response.status_code not in {
        200,
        201,
    }:

        print(
            "[ZOOM CHAT] Channel creation failed."
        )

        print(
            "[ZOOM CHAT] Status:",
            response.status_code,
        )

        print(
            "[ZOOM CHAT] Response:",
            data,
        )

        return {
            "success": False,
            "status_code": response.status_code,
            "error": (
                "Failed to create Zoom Team Chat channel."
            ),
            "details": data,
        }

    # ========================================================
    # CHANNEL ID
    # ========================================================

    channel_id = (
        data.get("id")
        or data.get("channel_id")
    )

    print(
        "✅ [ZOOM CHAT] Channel created successfully."
    )

    print(
        "[ZOOM CHAT] Channel ID:",
        channel_id,
    )

    return {
        "success": True,
        "status_code": response.status_code,
        "channel_id": channel_id,
        "channel": data,
    }


# ============================================================
# LIST CHANNELS
# ============================================================

def list_zoom_channels(
    page_size: int = 50,
):
    """
    Get channels available to the authenticated user.
    """

    page_size = max(
        1,
        min(page_size, 300),
    )

    url = (
        f"{ZOOM_API_BASE}"
        "/chat/users/me/channels"
    )

    params = {
        "page_size": page_size,
    }

    response, error = zoom_chat_request(
        "GET",
        url,
        params=params,
    )

    if error:
        return error

    try:

        data = response.json()

    except ValueError:

        data = {
            "raw_response": response.text
        }

    if response.status_code != 200:

        return {
            "success": False,
            "status_code": response.status_code,
            "error": (
                "Failed to retrieve "
                "Zoom Team Chat channels."
            ),
            "details": data,
        }

    channels = data.get(
        "channels",
        [],
    )

    return {
        "success": True,
        "status_code": 200,
        "channels": channels,
        "total": len(channels),
        "next_page_token": data.get(
            "next_page_token",
            "",
        ),
        "data": data,
    }


# ============================================================
# FIND CHANNEL
# ============================================================

def find_zoom_channel(
    channel_name: str,
):
    """
    Find a channel by exact name.
    """

    if not channel_name:

        return {
            "success": False,
            "status_code": 400,
            "error": "Channel name is required.",
        }

    result = list_zoom_channels()

    if not result.get("success"):
        return result

    target = (
        channel_name
        .strip()
        .lower()
    )

    for channel in result.get(
        "channels",
        [],
    ):

        channel_settings = channel.get(
            "channel_settings",
            {},
        )

        name = (
            channel.get("name")
            or channel_settings.get("name")
            or ""
        )

        if (
            str(name)
            .strip()
            .lower()
            == target
        ):

            return {
                "success": True,
                "found": True,
                "channel": channel,
                "channel_id": (
                    channel.get("id")
                    or channel.get("channel_id")
                ),
            }

    return {
        "success": True,
        "found": False,
        "channel": None,
        "channel_id": None,
    }


# ============================================================
# GET OR CREATE CHANNEL
# ============================================================

def get_or_create_zoom_channel(
    channel_name: str,
):

    existing = find_zoom_channel(
        channel_name
    )

    if not existing.get("success"):
        return existing

    if existing.get("found"):

        print(
            "[ZOOM CHAT] Existing channel found:",
            existing.get("channel_id"),
        )

        return {
            "success": True,
            "created": False,
            "channel": existing.get("channel"),
            "channel_id": existing.get(
                "channel_id"
            ),
        }

    print(
        "[ZOOM CHAT] Channel does not exist."
    )

    print(
        "[ZOOM CHAT] Creating channel:",
        channel_name,
    )

    created = create_zoom_channel(
        channel_name=channel_name,
        channel_type=3,
    )

    if not created.get("success"):
        return created

    return {
        "success": True,
        "created": True,
        "channel": created.get("channel"),
        "channel_id": created.get(
            "channel_id"
        ),
    }


# ============================================================
# SEND ZOOM CHAT MESSAGE
# ============================================================

def send_zoom_chat_message(
    message: str,
    to_contact: str | None = None,
    to_channel: str | None = None,
):
    """
    Send a Zoom Team Chat message.

    Exactly one destination must be provided.
    """

    if not message or not message.strip():

        return {
            "success": False,
            "status_code": 400,
            "error": "Message cannot be empty.",
        }

    message = message.strip()

    if not to_contact and not to_channel:

        return {
            "success": False,
            "status_code": 400,
            "error": (
                "You must provide either "
                "to_contact or to_channel."
            ),
        }

    if to_contact and to_channel:

        return {
            "success": False,
            "status_code": 400,
            "error": (
                "Provide only one destination."
            ),
        }

    # ========================================================
    # URL
    # ========================================================

    url = (
        f"{ZOOM_API_BASE}"
        "/chat/users/me/messages"
    )

    # ========================================================
    # PAYLOAD
    # ========================================================

    payload = {
        "message": message,
    }

    if to_contact:

        payload["to_contact"] = (
            to_contact.strip()
        )

    if to_channel:

        payload["to_channel"] = (
            to_channel.strip()
        )

    print(
        "[ZOOM CHAT] Sending message..."
    )

    response, error = zoom_chat_request(
        "POST",
        url,
        json=payload,
    )

    if error:
        return error

    try:

        data = response.json()

    except ValueError:

        data = {}

    if response.status_code not in {
        200,
        201,
        204,
    }:

        return {
            "success": False,
            "status_code": response.status_code,
            "error": (
                "Zoom Team Chat API request failed."
            ),
            "details": (
                data
                if data
                else response.text
            ),
        }

    print(
        "✅ [ZOOM CHAT] Message sent successfully."
    )

    return {
        "success": True,
        "status_code": response.status_code,
        "destination": (
            {
                "type": "channel",
                "value": to_channel,
            }
            if to_channel
            else {
                "type": "contact",
                "value": to_contact,
            }
        ),
        "data": data,
    }


# ============================================================
# SEND MEETING SUMMARY
# ============================================================

def send_meeting_summary_to_zoom(
    meeting_title: str,
    summary: str,
    key_points,
    decisions,
    open_questions,
    action_items,
    filename: str,
    channel_id: str | None = None,
):
    """
    Send AI meeting summary to Zoom Team Chat.
    """

    if not channel_id:

        channel_id = get_env(
            "ZOOM_CHAT_CHANNEL"
        )

    if not channel_id:

        return {
            "success": False,
            "status_code": 400,
            "error": (
                "ZOOM_CHAT_CHANNEL is not configured."
            ),
        }

    # ========================================================
    # FORMAT BULLETS
    # ========================================================

    def format_item(item):

        if isinstance(item, dict):

            task = item.get(
                "task",
                "",
            )

            owner = item.get(
                "owner",
                "Not specified",
            )

            due = item.get(
                "due_date",
                "Not specified",
            )

            if task:

                return (
                    f"{task}"
                    f" | Owner: {owner}"
                    f" | Due: {due}"
                )

            return json.dumps(
                item,
                ensure_ascii=False,
            )

        return str(item)

    def format_bullets(
        value,
        empty_text,
    ):

        if not value:
            return empty_text

        if isinstance(value, list):

            return "\n".join(
                f"• {format_item(item)}"
                for item in value
            )

        return str(value)

    key_points_text = format_bullets(
        key_points,
        "No key points found.",
    )

    decisions_text = format_bullets(
        decisions,
        "No decisions found.",
    )

    questions_text = format_bullets(
        open_questions,
        "No open questions.",
    )

    action_items_text = format_bullets(
        action_items,
        "No action items found.",
    )

    # ========================================================
    # MESSAGE
    # ========================================================

    message = (
        "🤖 AI Meeting Intelligence Assistant\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"📁 File\n"
        f"{filename}\n\n"

        f"📝 Meeting\n"
        f"{meeting_title}\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"📄 Summary\n"
        f"{summary or 'No summary available.'}\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"📌 Key Points\n"
        f"{key_points_text}\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"✅ Decisions\n"
        f"{decisions_text}\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"📋 Action Items\n"
        f"{action_items_text}\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"❓ Open Questions\n"
        f"{questions_text}\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "Generated automatically by "
        "AI Meeting Intelligence Assistant."
    )

    return send_zoom_chat_message(
        message=message,
        to_channel=channel_id,
    )


# ============================================================
# SEND TEST MESSAGE
# ============================================================

def send_test_zoom_message(
    channel_id: str | None = None,
):

    if not channel_id:

        channel_id = get_env(
            "ZOOM_CHAT_CHANNEL"
        )

    if not channel_id:

        return {
            "success": False,
            "status_code": 400,
            "error": (
                "ZOOM_CHAT_CHANNEL is not configured."
            ),
        }

    message = (
        "🤖 AI Meeting Intelligence Assistant\n\n"
        "✅ Zoom Team Chat integration is working.\n\n"
        "This is a test message."
    )

    return send_zoom_chat_message(
        message=message,
        to_channel=channel_id,
    )