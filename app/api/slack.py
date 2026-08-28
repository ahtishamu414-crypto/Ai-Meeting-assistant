import logging

from fastapi import APIRouter, Request

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