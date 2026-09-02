import asyncio
import logging
import os

from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from app.services.slack_huddle import (
    process_huddle_event,
    handle_participant_change
)


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger("slack_listener")


# ============================================================
# SLACK TOKENS
# ============================================================

SLACK_BOT_TOKEN = os.getenv(
    "SLACK_BOT_TOKEN"
)

SLACK_APP_TOKEN = os.getenv(
    "SLACK_APP_TOKEN"
)


# ============================================================
# VALIDATION
# ============================================================

if not SLACK_BOT_TOKEN:
    logger.warning(
        "SLACK_BOT_TOKEN is not configured."
    )

if not SLACK_APP_TOKEN:
    logger.warning(
        "SLACK_APP_TOKEN is not configured."
    )


# ============================================================
# SLACK APP
# ============================================================

slack_app = AsyncApp(
    token=SLACK_BOT_TOKEN
)


# ============================================================
# SOCKET MODE HANDLER
# ============================================================

socket_handler = None
slack_listener_task = None


# ============================================================
# HELPER
# ============================================================

def get_user_huddle_state(event):
    """
    Safely extract user Huddle state.

    Slack user_huddle_changed may provide data such as:

        {
            "user": {
                "id": "U123",
                "profile": {
                    "huddle_state": "in_a_huddle",
                    "huddle_state_call_id": "R123"
                }
            }
        }

    Depending on Slack event shape, user data may also be
    available directly.
    """

    if not isinstance(event, dict):
        return None, None, None

    # ========================================================
    # USER OBJECT
    # ========================================================

    user = event.get("user")

    if not isinstance(user, dict):
        user = {}

    # ========================================================
    # USER ID
    # ========================================================

    user_id = (
        event.get("user_id")
        or user.get("id")
    )

    # ========================================================
    # PROFILE
    # ========================================================

    profile = user.get(
        "profile",
        {}
    )

    if not isinstance(profile, dict):
        profile = {}

    # ========================================================
    # STATE
    # ========================================================

    huddle_state = (
        event.get("huddle_state")
        or profile.get("huddle_state")
    )

    # ========================================================
    # CALL ID
    # ========================================================

    huddle_call_id = (
        event.get("huddle_state_call_id")
        or profile.get("huddle_state_call_id")
    )

    return (
        user_id,
        huddle_state,
        huddle_call_id
    )


# ============================================================
# MESSAGE EVENTS
# ============================================================

@slack_app.event("message")
async def handle_message_events(
    body,
    event,
    logger
):
    """
    Handle Slack message events.

    Huddle system messages may arrive as:

        subtype=huddle_thread

    And the final Huddle state can later arrive as:

        subtype=message_changed
        subtype=message_deleted

    We process ALL three when Huddle room data exists.
    """

    try:

        if not isinstance(event, dict):
            return

        subtype = event.get(
            "subtype"
        )

        # ====================================================
        # IMPORTANT:
        # Do not only process huddle_thread.
        #
        # message_changed/message_deleted can contain the
        # final room.has_ended=True state.
        # ====================================================

        huddle_candidate = None

        # ----------------------------------------------------
        # Direct Huddle event
        # ----------------------------------------------------

        if subtype == "huddle_thread":

            huddle_candidate = event

        # ----------------------------------------------------
        # Changed/deleted Huddle message
        # ----------------------------------------------------

        elif subtype in (
            "message_changed",
            "message_deleted"
        ):

            huddle_candidate = event

        # ----------------------------------------------------
        # If this isn't an obvious Huddle event, still check
        # whether process_huddle_event can extract room data.
        # ----------------------------------------------------

        if huddle_candidate is None:
            return

        # ====================================================
        # CHECK FOR HUDDLE ROOM
        # ====================================================

        result = process_huddle_event(
            huddle_candidate
        )

        # ====================================================
        # RESULT
        # ====================================================

        if result:

            logger.info(
                "Huddle processed | "
                "mongo_id=%s | "
                "huddle_id=%s | "
                "status=%s | "
                "participants=%s | "
                "duration=%s",
                result.get("_id"),
                result.get("huddle_id"),
                result.get("status"),
                result.get("participants", []),
                result.get("duration_seconds")
            )

    except Exception:

        logger.exception(
            "Error processing Slack message event."
        )


# ============================================================
# USER HUDDLE CHANGED
# ============================================================

@slack_app.event("user_huddle_changed")
async def handle_user_huddle_changed(
    body,
    event,
    logger
):
    """
    Handle participant join/leave events.

    Join:

        huddle_state = in_a_huddle
        huddle_state_call_id = R123

    Leave:

        huddle_state = default_unset
        huddle_state_call_id = None

    IMPORTANT:

    On leave, NEVER manufacture a Huddle ID.

    The Huddle service will find the active Huddle
    using the user's participation record.
    """

    try:

        (
            user_id,
            huddle_state,
            huddle_call_id
        ) = get_user_huddle_state(
            event
        )

        logger.info(
            "User Huddle changed | "
            "user=%s | "
            "state=%s | "
            "call_id=%s",
            user_id,
            huddle_state,
            huddle_call_id
        )

        # ====================================================
        # VALIDATE USER
        # ====================================================

        if not user_id:

            logger.warning(
                "user_huddle_changed has no user ID."
            )

            return

        # ====================================================
        # JOIN
        # ====================================================

        if huddle_state == "in_a_huddle":

            result = handle_participant_change(
                user_id=user_id,
                huddle_id=huddle_call_id,
                huddle_state=huddle_state
            )

            if result:

                logger.info(
                    "Participant joined | "
                    "user=%s | "
                    "huddle=%s | "
                    "participants=%s",
                    user_id,
                    result.get("huddle_id"),
                    result.get("participants", [])
                )

            return

        # ====================================================
        # LEAVE
        # ====================================================

        if huddle_state == "default_unset":

            # IMPORTANT:
            #
            # Slack normally gives call_id=None here.
            #
            # Do NOT use a stale Huddle ID.
            #
            # Pass None and let slack_huddle.py resolve
            # the active Huddle from MongoDB.

            result = handle_participant_change(
                user_id=user_id,
                huddle_id=None,
                huddle_state=huddle_state
            )

            if result:

                logger.info(
                    "Participant left | "
                    "user=%s | "
                    "huddle=%s | "
                    "participants=%s | "
                    "active=%s",
                    user_id,
                    result.get("huddle_id"),
                    result.get("participants", []),
                    result.get(
                        "active_participants",
                        []
                    )
                )

            else:

                logger.info(
                    "Participant left | "
                    "user=%s | "
                    "no active Huddle found | "
                    "call_id=None",
                    user_id
                )

            return

        # ====================================================
        # UNKNOWN STATE
        # ====================================================

        logger.info(
            "Ignoring unknown Huddle state | "
            "user=%s | "
            "state=%s",
            user_id,
            huddle_state
        )

    except Exception:

        logger.exception(
            "Error processing user_huddle_changed."
        )


# ============================================================
# START SOCKET MODE
# ============================================================

async def start_slack_listener():
    """
    Start Slack Socket Mode listener.
    """

    global socket_handler

    if not SLACK_APP_TOKEN:

        logger.error(
            "SLACK_APP_TOKEN is missing. "
            "Cannot start Slack Socket Mode."
        )

        return

    try:

        from slack_bolt.adapter.socket_mode.async_handler import (
            AsyncSocketModeHandler
        )

        socket_handler = AsyncSocketModeHandler(
            slack_app,
            SLACK_APP_TOKEN
        )

        logger.info(
            "Slack listener started."
        )

        logger.info(
            "Starting Slack Socket Mode..."
        )

        await socket_handler.start_async()

    except asyncio.CancelledError:

        logger.info(
            "Slack listener task cancelled."
        )

        raise

    except Exception:

        logger.exception(
            "Slack Socket Mode failed."
        )

        raise


# ============================================================
# STOP SOCKET MODE
# ============================================================

async def stop_slack_listener():
    """
    Stop Slack Socket Mode listener.
    """

    global socket_handler

    logger.info(
        "Stopping Slack listener..."
    )

    if socket_handler:

        try:

            await socket_handler.close_async()

        except Exception:

            logger.exception(
                "Error while stopping Slack listener."
            )

        finally:

            socket_handler = None

    logger.info(
        "Slack listener stopped."
    )


# ============================================================
# BACKGROUND TASK
# ============================================================

async def run_slack_listener():
    """
    Run Socket Mode as a background task.
    """

    global slack_listener_task

    logger.info(
        "Slack listener started in background."
    )

    try:

        await start_slack_listener()

    except asyncio.CancelledError:

        logger.info(
            "Slack listener background task cancelled."
        )

        raise

    except Exception:

        logger.exception(
            "Slack listener crashed."
        )

    finally:

        logger.info(
            "Slack listener background task stopped."
        )


# ============================================================
# CREATE TASK
# ============================================================

def create_slack_listener_task():
    """
    Create background Slack listener task.
    """

    global slack_listener_task

    if slack_listener_task:

        logger.warning(
            "Slack listener task already exists."
        )

        return slack_listener_task

    slack_listener_task = asyncio.create_task(
        run_slack_listener()
    )

    return slack_listener_task


# ============================================================
# CANCEL TASK
# ============================================================

async def cancel_slack_listener_task():
    """
    Cancel background Slack listener task.
    """

    global slack_listener_task

    if not slack_listener_task:
        return

    if not slack_listener_task.done():

        slack_listener_task.cancel()

        try:

            await slack_listener_task

        except asyncio.CancelledError:

            pass

    slack_listener_task = None