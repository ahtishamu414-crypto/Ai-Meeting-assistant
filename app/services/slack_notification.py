import logging
import os
from datetime import datetime, timezone

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from app.database import slack_meetings_collection


logger = logging.getLogger("slack_notification")


# ============================================================
# SLACK CLIENT
# ============================================================
#
# A plain synchronous WebClient, built from the same
# SLACK_BOT_TOKEN already used by the Socket Mode listener
# (app/services/slack_listener.py). It is intentionally NOT
# the same client instance as slack_app.client: that one is an
# AsyncWebClient bound to the listener's asyncio event loop,
# while this module is called from _run_pipeline's background
# thread (app/services/slack_pipeline.py) and needs a client
# that is safe to use from plain sync code.

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

_client = None


def _get_client():
    """
    Lazily build the Slack WebClient.

    Lazy + module-level singleton so importing this module
    never fails just because SLACK_BOT_TOKEN happens to be
    unset in some environment (e.g. running tests).
    """

    global _client

    if _client is None and SLACK_BOT_TOKEN:
        _client = WebClient(token=SLACK_BOT_TOKEN)

    return _client


# ============================================================
# MESSAGE BUILDER
# ============================================================

def _bullet_list(items):
    lines = []

    for item in items or []:

        if isinstance(item, dict):
            text = item.get("task") or item.get("text") or str(item)
        else:
            text = str(item)

        text = text.strip()

        if text:
            lines.append(f"• {text}")

    return lines


def build_meeting_message(meeting):
    """
    Build the Slack DM text for a completed meeting.

    Only includes sections for which the meeting document
    actually has data - never fabricates content.
    """

    lines = ["\U0001F4CB *Meeting Summary*", ""]

    title = meeting.get("meeting_title")
    lines.append(f"*Meeting:* {title.strip()}" if title and title.strip() else "*Meeting:* Slack Huddle")

    summary = (meeting.get("summary") or "").strip()

    if summary:
        lines += ["", "*Summary:*", summary]

    key_points = _bullet_list(meeting.get("key_points"))

    if key_points:
        lines += ["", "*Key Points:*", *key_points]

    action_items = meeting.get("action_items") or []
    action_lines = []

    for item in action_items:

        if isinstance(item, dict):

            task = (item.get("task") or "").strip()

            if not task:
                continue

            owner = item.get("owner") or "Not specified"
            due = item.get("due_date") or "Not specified"
            jira_key = item.get("jira_key")

            line = f"• {task} (Owner: {owner}, Due: {due})"

            if jira_key:
                line += f" [{jira_key}]"

            action_lines.append(line)

        else:
            text = str(item).strip()

            if text:
                action_lines.append(f"• {text}")

    if action_lines:
        lines += ["", "*Action Items:*", *action_lines]

    decisions = _bullet_list(meeting.get("decisions"))

    if decisions:
        lines += ["", "*Decisions:*", *decisions]

    open_questions = _bullet_list(meeting.get("open_questions"))

    if open_questions:
        lines += ["", "*Open Questions:*", *open_questions]

    jira_keys = sorted({
        item.get("jira_key")
        for item in action_items
        if isinstance(item, dict) and item.get("jira_key")
    })

    if jira_keys:
        lines += ["", "*Jira:*", ", ".join(jira_keys)]

    return "\n".join(lines)


# ============================================================
# SEND TO ONE PARTICIPANT
# ============================================================

def _send_to_user(client, huddle_id, user_id, text):
    """
    Open (or reuse) a DM with one Slack user and send the
    message. Returns True on success, False on failure.
    Never raises - all Slack/network errors are caught here so
    one participant's failure cannot stop the others.
    """

    logger.info(
        "[SLACK NOTIFICATION] Sending | huddle=%s | user=%s",
        huddle_id,
        user_id
    )

    try:

        opened = client.conversations_open(users=[user_id])
        channel_id = opened["channel"]["id"]

        client.chat_postMessage(
            channel=channel_id,
            text=text
        )

        logger.info(
            "[SLACK NOTIFICATION] Sent | huddle=%s | user=%s",
            huddle_id,
            user_id
        )

        return True, None

    except SlackApiError as e:

        error = e.response.get("error", str(e)) if e.response else str(e)

        logger.error(
            "[SLACK NOTIFICATION] Failed | huddle=%s | user=%s | error=%s",
            huddle_id,
            user_id,
            error
        )

        return False, error

    except Exception as e:

        logger.error(
            "[SLACK NOTIFICATION] Failed | huddle=%s | user=%s | error=%s",
            huddle_id,
            user_id,
            e
        )

        return False, str(e)


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def send_meeting_summary_to_participants(meeting):
    """
    Send the completed meeting's summary to every Slack
    participant as a DM.

    Safe to call multiple times for the same huddle: a
    participant who was already sent this meeting's summary
    (per meeting["notifications"][user_id]["status"] == "sent")
    is skipped, so a duplicate huddle-ended event or a retried
    pipeline run cannot double-DM anyone.

    Never raises. A Slack failure is logged and recorded per
    participant; it must never affect processing_status, which
    the caller has already set to "completed" before invoking
    this function.
    """

    if not isinstance(meeting, dict):

        logger.error(
            "[SLACK NOTIFICATION] Skipped | reason=invalid meeting data"
        )

        return

    huddle_id = meeting.get("huddle_id")

    participants = meeting.get("participants") or []

    # ----------------------------------------------------
    # Dedupe while preserving order. participants is already
    # deduped upstream (normalize_participants /
    # merge_participants in slack_huddle.py) - this is just a
    # defensive second pass so this service never trusts that
    # invariant blindly.
    # ----------------------------------------------------

    seen = set()
    unique_participants = []

    for user_id in participants:

        user_id = str(user_id or "").strip()

        if user_id and user_id not in seen:
            seen.add(user_id)
            unique_participants.append(user_id)

    if not unique_participants:

        logger.info(
            "[SLACK NOTIFICATION] Skipped | huddle=%s | reason=no participants",
            huddle_id
        )

        return

    client = _get_client()

    if client is None:

        logger.error(
            "[SLACK NOTIFICATION] Skipped | huddle=%s | "
            "reason=SLACK_BOT_TOKEN not configured",
            huddle_id
        )

        return

    # ----------------------------------------------------
    # IDEMPOTENCY: skip participants already notified for
    # this meeting.
    # ----------------------------------------------------

    existing_notifications = meeting.get("notifications") or {}

    if not isinstance(existing_notifications, dict):
        existing_notifications = {}

    pending_participants = [
        user_id
        for user_id in unique_participants
        if existing_notifications.get(user_id, {}).get("status") != "sent"
    ]

    already_sent = len(unique_participants) - len(pending_participants)

    if not pending_participants:

        logger.info(
            "[SLACK NOTIFICATION] Skipped | huddle=%s | "
            "reason=all participants already notified",
            huddle_id
        )

        return

    logger.info(
        "[SLACK NOTIFICATION] Started | huddle=%s | participants=%s",
        huddle_id,
        len(pending_participants)
    )

    if already_sent:

        logger.info(
            "[SLACK NOTIFICATION] Skipping already-notified participants | "
            "huddle=%s | count=%s",
            huddle_id,
            already_sent
        )

    text = build_meeting_message(meeting)

    sent_count = 0
    failed_count = 0
    notification_updates = {}

    for user_id in pending_participants:

        success, error = _send_to_user(client, huddle_id, user_id, text)

        now = datetime.now(timezone.utc)

        if success:

            sent_count += 1

            notification_updates[f"notifications.{user_id}"] = {
                "status": "sent",
                "sent_at": now,
            }

        else:

            failed_count += 1

            notification_updates[f"notifications.{user_id}"] = {
                "status": "failed",
                "sent_at": now,
                "error": error,
            }

    # ----------------------------------------------------
    # PERSIST NOTIFICATION RESULTS
    # ----------------------------------------------------
    #
    # A dedicated field, never touching transcript/summary/
    # action_items/embedding. notification_status is a
    # coarse rollup for quick querying; per-user detail lives
    # under "notifications".

    if unique_participants and (sent_count + already_sent) == len(unique_participants):
        rollup_status = "sent"
    elif sent_count > 0:
        rollup_status = "partial"
    else:
        rollup_status = "failed"

    try:

        slack_meetings_collection.update_one(
            {"huddle_id": huddle_id},
            {
                "$set": {
                    **notification_updates,
                    "notification_status": rollup_status,
                    "notification_updated_at": datetime.now(timezone.utc),
                }
            }
        )

    except Exception:

        logger.exception(
            "[SLACK NOTIFICATION] Failed to persist notification status | "
            "huddle=%s",
            huddle_id
        )

    logger.info(
        "[SLACK NOTIFICATION] Completed | huddle=%s | sent=%s | failed=%s",
        huddle_id,
        sent_count,
        failed_count
    )
