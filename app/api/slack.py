import logging

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Request

from app.database import slack_meetings_collection
from app.services.slack_huddle import (
    process_huddle_event
)


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger("slack_api")


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/slack",
    tags=["Slack"]
)


# ============================================================
# SERIALIZE SLACK MEETING
# ============================================================

def serialize_slack_meeting(meeting):
    """
    Build a consistent API response for a Slack Huddle meeting.
    """

    return {
        "meeting_id":
            str(meeting.get("_id")),

        "huddle_id":
            meeting.get("huddle_id"),

        "channel_id":
            meeting.get("channel_id"),

        "status":
            meeting.get("status", "active"),

        "processing_status":
            meeting.get("processing_status", "pending"),

        "started_at":
            meeting.get("started_at"),

        "ended_at":
            meeting.get("ended_at"),

        "duration_seconds":
            meeting.get("duration_seconds"),

        "participants":
            meeting.get("participants", []),

        "summary":
            meeting.get("summary"),

        "topics":
            meeting.get("topics", []),

        "decisions":
            meeting.get("decisions", []),

        "open_questions":
            meeting.get("open_questions", []),

        "key_points":
            meeting.get("key_points", []),

        "action_items":
            meeting.get("action_items", []),

        "transcript":
            meeting.get("transcript"),
    }


# ============================================================
# LIST SLACK HUDDLE MEETINGS
# ============================================================

@router.get("/meetings")
async def list_slack_meetings():
    """
    Return all Slack Huddle meetings, most recent first.
    """

    meetings = list(
        slack_meetings_collection.find({}).sort(
            "started_at",
            -1
        )
    )

    results = [
        serialize_slack_meeting(meeting)
        for meeting in meetings
    ]

    return {
        "count": len(results),
        "meetings": results,
    }


# ============================================================
# GET SINGLE SLACK MEETING
# ============================================================

@router.get("/meetings/{meeting_id}")
async def get_slack_meeting(meeting_id: str):
    """
    Return a single Slack Huddle meeting by its Mongo ID.
    """

    try:

        object_id = ObjectId(meeting_id)

    except InvalidId:

        raise HTTPException(
            status_code=400,
            detail="Invalid meeting_id."
        )

    meeting = slack_meetings_collection.find_one({
        "_id": object_id
    })

    if not meeting:

        raise HTTPException(
            status_code=404,
            detail="Slack meeting not found."
        )

    return serialize_slack_meeting(meeting)


# ============================================================
# SLACK EVENTS
# ============================================================

@router.post("/events")
async def slack_events(
    request: Request
):
    """
    Main Slack Events API endpoint.

    Handles:

        1. Slack URL verification
        2. Huddle lifecycle events
        3. Participant changes
    """

    # ========================================================
    # READ BODY
    # ========================================================

    try:

        payload = await request.json()

    except Exception as exc:

        logger.exception(
            "❌ Failed to parse Slack request."
        )

        return {
            "ok": False,
            "error": "invalid_json"
        }

    # ========================================================
    # LOG PAYLOAD
    # ========================================================

    logger.info(
        "=================================================="
    )

    logger.info(
        "📦 SLACK EVENT RECEIVED"
    )

    logger.info(
        "%s",
        payload
    )

    logger.info(
        "=================================================="
    )

    # ========================================================
    # SLACK URL VERIFICATION
    # ========================================================

    if payload.get("type") == "url_verification":

        challenge = payload.get(
            "challenge"
        )

        logger.info(
            "🔐 Slack URL verification request."
        )

        return {
            "challenge": challenge
        }

    # ========================================================
    # EVENT CALLBACK
    # ========================================================

    if payload.get("type") == "event_callback":

        event = payload.get(
            "event",
            {}
        )

        if not isinstance(event, dict):

            logger.warning(
                "⚠️ Slack event is not a dictionary."
            )

            return {
                "ok": True
            }

        # ----------------------------------------------------
        # Event type
        # ----------------------------------------------------

        event_type = event.get(
            "type"
        )

        logger.info(
            "🔎 Slack event type: %s",
            event_type
        )

        # ----------------------------------------------------
        # Huddle processing
        # ----------------------------------------------------

        try:

            result = process_huddle_event(
                event
            )

            if result:

                logger.info(
                    "✅ Huddle event processed successfully."
                )

            else:

                logger.info(
                    "ℹ️ Huddle event did not modify "
                    "a meeting."
                )

        except Exception:

            logger.exception(
                "❌ Error processing Slack Huddle event."
            )

        # ----------------------------------------------------
        # Always acknowledge Slack
        # ----------------------------------------------------

        return {
            "ok": True
        }

    # ========================================================
    # UNKNOWN SLACK REQUEST
    # ========================================================

    logger.info(
        "ℹ️ Unknown Slack request type: %s",
        payload.get("type")
    )

    return {
        "ok": True
    }