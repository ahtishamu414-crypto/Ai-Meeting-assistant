import logging
from datetime import datetime, timezone

from app.database import db


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger("slack_huddle")


# ============================================================
# MONGODB COLLECTION
# ============================================================

slack_meetings_collection = db["slack_meetings"]


# ============================================================
# DATETIME HELPERS
# ============================================================

def ensure_utc_datetime(value):
    """
    Convert datetime into timezone-aware UTC datetime.

    MongoDB/PyMongo may return naive datetime objects.
    """

    if value is None:
        return None

    if not isinstance(value, datetime):
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def unix_to_datetime(timestamp):
    """
    Convert Slack Unix timestamp into UTC datetime.

    Supports:
        1787910850
        "1787910850"
        "1787910850.123456"

    Returns None for invalid/zero values.
    """

    if timestamp is None:
        return None

    try:
        timestamp = float(timestamp)

        # Slack uses 0 when no end timestamp exists.
        if timestamp <= 0:
            return None

        return datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc
        )

    except (
        ValueError,
        TypeError,
        OverflowError
    ):
        return None


# ============================================================
# PARTICIPANT HELPERS
# ============================================================

def normalize_participants(participants):
    """
    Normalize participant data into unique Slack user IDs.
    """

    if not isinstance(participants, list):
        return []

    normalized = []

    for participant in participants:

        # ----------------------------------------------------
        # String
        # ----------------------------------------------------

        if isinstance(participant, str):

            user_id = participant.strip()

            if user_id and user_id not in normalized:
                normalized.append(user_id)

        # ----------------------------------------------------
        # Dictionary
        # ----------------------------------------------------

        elif isinstance(participant, dict):

            user_id = (
                participant.get("id")
                or participant.get("user_id")
                or participant.get("user")
            )

            if isinstance(user_id, str):
                user_id = user_id.strip()

            if user_id and user_id not in normalized:
                normalized.append(user_id)

    return normalized


def merge_participants(*participant_lists):
    """
    Merge participant lists while preserving order
    and removing duplicates.
    """

    merged = []

    for participants in participant_lists:

        for user_id in normalize_participants(participants):

            if user_id not in merged:
                merged.append(user_id)

    return merged


# ============================================================
# DURATION
# ============================================================

def calculate_duration(started_at, ended_at):
    """
    Calculate Huddle duration in seconds.
    """

    started_at = ensure_utc_datetime(started_at)
    ended_at = ensure_utc_datetime(ended_at)

    if started_at is None or ended_at is None:
        return None

    try:

        duration = int(
            (
                ended_at - started_at
            ).total_seconds()
        )

        return max(0, duration)

    except (
        TypeError,
        ValueError,
        AttributeError
    ):

        logger.exception(
            "Failed to calculate Huddle duration."
        )

        return None


# ============================================================
# FIND ACTIVE HUDDLE
# ============================================================

def find_active_huddle(
    huddle_id=None,
    user_id=None
):
    """
    Find the currently active Huddle.

    Priority:

        1. Exact huddle_id
        2. User inside active_participants
        3. User inside participants
        4. Creator fallback

    active_participants is preferred because it tells us
    who is currently inside the Huddle.

    participants is permanent meeting history.
    """

    # ========================================================
    # 1. EXACT HUDDLE ID
    # ========================================================

    if huddle_id:

        meeting = slack_meetings_collection.find_one(
            {
                "huddle_id": huddle_id,
                "status": "active"
            }
        )

        if meeting:
            return meeting

    # ========================================================
    # 2. ACTIVE PARTICIPANTS
    # ========================================================

    if user_id:

        meeting = slack_meetings_collection.find_one(
            {
                "status": "active",
                "active_participants": user_id
            },
            sort=[
                ("started_at", -1)
            ]
        )

        if meeting:
            return meeting

        # ====================================================
        # 3. HISTORICAL PARTICIPANTS
        # ====================================================

        meeting = slack_meetings_collection.find_one(
            {
                "status": "active",
                "participants": user_id
            },
            sort=[
                ("started_at", -1)
            ]
        )

        if meeting:
            return meeting

        # ====================================================
        # 4. CREATOR FALLBACK
        # ====================================================

        meeting = slack_meetings_collection.find_one(
            {
                "status": "active",
                "creator_id": user_id
            },
            sort=[
                ("started_at", -1)
            ]
        )

        if meeting:
            return meeting

    return None


# ============================================================
# HUDDLE STARTED
# ============================================================

def handle_huddle_started(event):
    """
    Create or update a Slack Huddle.

    An ended Huddle is NEVER reopened.
    """

    if not isinstance(event, dict):

        logger.warning(
            "Invalid Huddle start event."
        )

        return None

    room = event.get("room", {})

    if not isinstance(room, dict):
        room = {}

    # ========================================================
    # EXTRACT
    # ========================================================

    huddle_id = room.get("id")

    channels = room.get("channels", [])

    channel_id = (
        event.get("channel")
        or (
            channels[0]
            if isinstance(channels, list) and channels
            else None
        )
    )

    creator_id = room.get("created_by")

    started_timestamp = room.get("date_start")

    huddle_link = room.get("huddle_link")

    external_unique_id = room.get(
        "external_unique_id"
    )

    participants = normalize_participants(
        room.get(
            "participant_history",
            []
        )
    )

    # ========================================================
    # VALIDATION
    # ========================================================

    if not huddle_id:

        logger.warning(
            "Huddle start event has no room.id."
        )

        return None

    now = datetime.now(timezone.utc)

    started_at = (
        unix_to_datetime(started_timestamp)
        or now
    )

    # ========================================================
    # ALREADY ENDED
    # ========================================================

    if room.get("has_ended") is True:

        logger.warning(
            "Huddle %s arrived already ended.",
            huddle_id
        )

        return handle_huddle_ended(event)

    # ========================================================
    # FIND EXISTING HUDDLE
    # ========================================================

    existing = slack_meetings_collection.find_one(
        {
            "huddle_id": huddle_id
        }
    )

    # ========================================================
    # EXISTING HUDDLE
    # ========================================================

    if existing:

        # ----------------------------------------------------
        # NEVER REOPEN ENDED HUDDLE
        # ----------------------------------------------------

        if existing.get("status") == "ended":

            logger.warning(
                "Huddle %s already ended. Not reopening.",
                huddle_id
            )

            return existing

        # ----------------------------------------------------
        # UPDATE ACTIVE HUDDLE
        # ----------------------------------------------------

        update_data = {
            "updated_at": now
        }

        if channel_id:
            update_data["channel_id"] = channel_id

        if creator_id:
            update_data["creator_id"] = creator_id

        if huddle_link:
            update_data["huddle_link"] = huddle_link

        if external_unique_id:
            update_data["external_unique_id"] = (
                external_unique_id
            )

        update_operation = {
            "$set": update_data
        }

        if participants:

            update_operation["$addToSet"] = {
                "participants": {
                    "$each": participants
                },
                "active_participants": {
                    "$each": participants
                }
            }

        slack_meetings_collection.update_one(
            {
                "_id": existing["_id"]
            },
            update_operation
        )

        updated = slack_meetings_collection.find_one(
            {
                "_id": existing["_id"]
            }
        )

        logger.info(
            "Existing Huddle updated | huddle=%s",
            huddle_id
        )

        return updated

    # ========================================================
    # NEW HUDDLE
    # ========================================================

    meeting = {

        # ----------------------------------------------------
        # IDENTITY
        # ----------------------------------------------------

        "meeting_type": "slack_huddle",

        "huddle_id": huddle_id,

        "external_unique_id": external_unique_id,

        "channel_id": channel_id,

        "creator_id": creator_id,

        "huddle_link": huddle_link,

        # ----------------------------------------------------
        # LIFECYCLE
        # ----------------------------------------------------

        "started_at": started_at,

        "ended_at": None,

        "duration_seconds": None,

        "status": "active",

        # ----------------------------------------------------
        # PARTICIPANTS
        # ----------------------------------------------------

        # Permanent meeting history
        "participants": participants,

        # Currently inside Huddle
        "active_participants": participants.copy(),

        # ----------------------------------------------------
        # PROCESSING
        # ----------------------------------------------------

        "processing_status": "pending",

        # ----------------------------------------------------
        # AI FIELDS
        # ----------------------------------------------------

        "audio_file": None,

        "transcript": None,

        "summary": None,

        "topics": [],

        "decisions": [],

        "open_questions": [],

        "key_points": [],

        "action_items": [],

        "embedding": None,

        # ----------------------------------------------------
        # TIMESTAMPS
        # ----------------------------------------------------

        "created_at": now,

        "updated_at": now
    }

    # ========================================================
    # INSERT
    # ========================================================

    result = slack_meetings_collection.insert_one(
        meeting
    )

    meeting["_id"] = result.inserted_id

    # ========================================================
    # LOG
    # ========================================================

    logger.info(
        "SLACK HUDDLE CREATED | "
        "mongo_id=%s | "
        "huddle_id=%s | "
        "channel=%s | "
        "creator=%s | "
        "participants=%s",
        result.inserted_id,
        huddle_id,
        channel_id,
        creator_id,
        participants
    )

    return meeting


# ============================================================
# PARTICIPANT JOIN
# ============================================================

def add_participant(
    user_id,
    huddle_id=None
):
    """
    Add user to an active Huddle.

    participants:
        Permanent meeting history.

    active_participants:
        Users currently inside the Huddle.
    """

    if not user_id:

        logger.warning(
            "Participant join has no user ID."
        )

        return None

    meeting = find_active_huddle(
        huddle_id=huddle_id,
        user_id=user_id
    )

    if not meeting:

        logger.warning(
            "No active Huddle found for participant=%s "
            "huddle_id=%s",
            user_id,
            huddle_id
        )

        return None

    actual_huddle_id = meeting.get("huddle_id")

    slack_meetings_collection.update_one(
        {
            "_id": meeting["_id"],
            "status": "active"
        },
        {
            "$addToSet": {
                "participants": user_id,
                "active_participants": user_id
            },
            "$set": {
                "updated_at": datetime.now(
                    timezone.utc
                )
            }
        }
    )

    updated = slack_meetings_collection.find_one(
        {
            "_id": meeting["_id"]
        }
    )

    logger.info(
        "Participant JOINED | user=%s | huddle=%s",
        user_id,
        actual_huddle_id
    )

    logger.info(
        "Participants=%s | active=%s",
        updated.get("participants", []),
        updated.get("active_participants", [])
    )

    return updated


# ============================================================
# PARTICIPANT LEAVE
# ============================================================

def remove_participant(
    user_id,
    huddle_id=None
):
    """
    Handle participant leaving.

    IMPORTANT:

    The user is removed from active_participants,
    but NOT from participants.

    participants = everyone who participated.
    active_participants = users currently inside.
    """

    if not user_id:

        logger.warning(
            "Participant leave has no user ID."
        )

        return None

    meeting = find_active_huddle(
        huddle_id=huddle_id,
        user_id=user_id
    )

    if not meeting:

        logger.info(
            "No active Huddle found for user=%s | call_id=%s",
            user_id,
            huddle_id
        )

        return None

    actual_huddle_id = meeting.get(
        "huddle_id"
    )

    # ========================================================
    # REMOVE ONLY FROM ACTIVE PARTICIPANTS
    # ========================================================

    slack_meetings_collection.update_one(
        {
            "_id": meeting["_id"],
            "status": "active"
        },
        {
            "$pull": {
                "active_participants": user_id
            },
            "$set": {
                "updated_at": datetime.now(
                    timezone.utc
                )
            }
        }
    )

    updated = slack_meetings_collection.find_one(
        {
            "_id": meeting["_id"]
        }
    )

    logger.info(
        "Participant LEFT | user=%s | huddle=%s",
        user_id,
        actual_huddle_id
    )

    logger.info(
        "Participant retained in meeting history."
    )

    logger.info(
        "Participants=%s | active=%s",
        updated.get("participants", []),
        updated.get("active_participants", [])
    )

    return updated


# ============================================================
# PARTICIPANT CHANGE
# ============================================================

def handle_participant_change(
    user_id,
    huddle_id,
    huddle_state
):
    """
    Handle Slack user_huddle_changed.

    States:

        in_a_huddle
        default_unset

    Slack commonly provides:

        default_unset
        huddle_call_id = None

    Therefore the leave handler resolves the active Huddle
    from MongoDB when no call ID is available.
    """

    if not user_id:

        logger.warning(
            "Participant change has no user ID."
        )

        return None

    # ========================================================
    # JOIN
    # ========================================================

    if huddle_state == "in_a_huddle":

        return add_participant(
            user_id=user_id,
            huddle_id=huddle_id
        )

    # ========================================================
    # LEAVE
    # ========================================================

    if huddle_state == "default_unset":

        return remove_participant(
            user_id=user_id,
            huddle_id=huddle_id
        )

    # ========================================================
    # UNKNOWN
    # ========================================================

    logger.info(
        "Unknown Huddle state | state=%s | user=%s",
        huddle_state,
        user_id
    )

    return None


# ============================================================
# HUDDLE ENDED
# ============================================================

def handle_huddle_ended(event):
    """
    Mark Huddle as ended.

    The primary signal is:

        room.has_ended == True

    This function is idempotent, so both:

        message_changed

    and:

        message_deleted

    can safely be processed.
    """

    if not isinstance(event, dict):

        logger.warning(
            "Invalid Huddle ended event."
        )

        return None

    room = event.get("room", {})

    if not isinstance(room, dict):
        room = {}

    # ========================================================
    # HUDDLE ID
    # ========================================================

    huddle_id = room.get("id")

    if not huddle_id:

        logger.warning(
            "Huddle ended event has no room.id."
        )

        return None

    # ========================================================
    # FIND MEETING
    # ========================================================

    meeting = slack_meetings_collection.find_one(
        {
            "huddle_id": huddle_id
        }
    )

    if not meeting:

        logger.error(
            "Huddle ended but no MongoDB meeting exists | "
            "huddle=%s",
            huddle_id
        )

        return None

    # ========================================================
    # SLACK PARTICIPANTS
    # ========================================================

    slack_participants = normalize_participants(
        room.get(
            "participant_history",
            []
        )
    )

    # ========================================================
    # MONGO PARTICIPANTS
    # ========================================================

    tracked_participants = normalize_participants(
        meeting.get(
            "participants",
            []
        )
    )

    # ========================================================
    # MERGE
    # ========================================================

    final_participants = merge_participants(
        tracked_participants,
        slack_participants
    )

    # ========================================================
    # ALREADY ENDED
    # ========================================================

    if meeting.get("status") == "ended":

        logger.info(
            "Huddle already ended | huddle=%s",
            huddle_id
        )

        # Still merge any participants discovered
        # in the final Slack event.

        if final_participants != tracked_participants:

            slack_meetings_collection.update_one(
                {
                    "_id": meeting["_id"]
                },
                {
                    "$set": {
                        "participants": final_participants,
                        "active_participants": [],
                        "updated_at": datetime.now(
                            timezone.utc
                        )
                    }
                }
            )

            meeting = slack_meetings_collection.find_one(
                {
                    "_id": meeting["_id"]
                }
            )

        return meeting

    # ========================================================
    # START TIME
    # ========================================================

    started_at = ensure_utc_datetime(
        meeting.get("started_at")
    )

    # ========================================================
    # END TIME
    # ========================================================

    ended_at = unix_to_datetime(
        room.get("date_end")
    )

    if not ended_at:

        ended_at = datetime.now(
            timezone.utc
        )

        logger.warning(
            "Slack date_end missing. "
            "Using current UTC time."
        )

    # ========================================================
    # DURATION
    # ========================================================

    duration_seconds = calculate_duration(
        started_at,
        ended_at
    )

    # ========================================================
    # UPDATE
    # ========================================================

    update_data = {

        "status": "ended",

        "ended_at": ended_at,

        "duration_seconds": duration_seconds,

        "participants": final_participants,

        # Nobody is active after the Huddle ends.
        "active_participants": [],

        "processing_status": "pending",

        "updated_at": datetime.now(
            timezone.utc
        )
    }

    slack_meetings_collection.update_one(
        {
            "_id": meeting["_id"],
            "status": "active"
        },
        {
            "$set": update_data
        }
    )

    # ========================================================
    # GET UPDATED
    # ========================================================

    updated = slack_meetings_collection.find_one(
        {
            "_id": meeting["_id"]
        }
    )

    # ========================================================
    # LOG
    # ========================================================

    logger.info(
        "SLACK HUDDLE ENDED | "
        "huddle=%s | "
        "started=%s | "
        "ended=%s | "
        "duration=%ss | "
        "participants=%s",
        huddle_id,
        started_at,
        ended_at,
        duration_seconds,
        final_participants
    )

    return updated


# ============================================================
# EXTRACT HUDDLE MESSAGE
# ============================================================

def extract_huddle_message(event):
    """
    Extract Huddle data from:

        1. event["room"]
        2. event["message"]["room"]
        3. event["previous_message"]["room"]
    """

    if not isinstance(event, dict):
        return None

    # ========================================================
    # 1. DIRECT EVENT
    # ========================================================

    room = event.get("room")

    if isinstance(room, dict) and room.get("id"):
        return event

    # ========================================================
    # 2. message_changed
    # ========================================================

    message = event.get("message")

    if isinstance(message, dict):

        nested_room = message.get("room")

        if (
            isinstance(nested_room, dict)
            and nested_room.get("id")
        ):
            return message

    # ========================================================
    # 3. message_deleted
    # ========================================================

    previous_message = event.get(
        "previous_message"
    )

    if isinstance(previous_message, dict):

        nested_room = previous_message.get("room")

        if (
            isinstance(nested_room, dict)
            and nested_room.get("id")
        ):
            return previous_message

    return None


# ============================================================
# HUDDLE EVENT ROUTER
# ============================================================

def process_huddle_event(event):
    """
    Main Slack Huddle lifecycle router.

    Priority:

        1. room.has_ended
        2. explicit huddle.ended
        3. huddle.started
    """

    if not isinstance(event, dict):

        logger.warning(
            "Invalid Huddle event."
        )

        return None

    # ========================================================
    # EXTRACT
    # ========================================================

    huddle_event = extract_huddle_message(
        event
    )

    if not huddle_event:

        logger.info(
            "No Huddle room data found."
        )

        return None

    # ========================================================
    # ROOM
    # ========================================================

    room = huddle_event.get(
        "room",
        {}
    )

    if not isinstance(room, dict):
        return None

    # ========================================================
    # METADATA
    # ========================================================

    metadata = huddle_event.get(
        "metadata",
        {}
    )

    if not isinstance(metadata, dict):
        metadata = {}

    event_type = metadata.get(
        "event_type"
    )

    # ========================================================
    # LOG
    # ========================================================

    logger.info(
        "Huddle event | "
        "event=%s | "
        "huddle=%s | "
        "ended=%s | "
        "start=%s | "
        "end=%s | "
        "participants=%s",
        event_type,
        room.get("id"),
        room.get("has_ended"),
        room.get("date_start"),
        room.get("date_end"),
        room.get("participant_history", [])
    )

    # ========================================================
    # 1. END FROM ROOM STATE
    # ========================================================

    if room.get("has_ended") is True:

        logger.info(
            "Huddle END detected from has_ended=True | "
            "huddle=%s",
            room.get("id")
        )

        return handle_huddle_ended(
            huddle_event
        )

    # ========================================================
    # 2. EXPLICIT END
    # ========================================================

    if event_type == "slack_system.huddle.ended":

        logger.info(
            "Explicit Huddle END event | huddle=%s",
            room.get("id")
        )

        return handle_huddle_ended(
            huddle_event
        )

    # ========================================================
    # 3. START
    # ========================================================

    if event_type == "slack_system.huddle.started":

        logger.info(
            "Explicit Huddle START event | huddle=%s",
            room.get("id")
        )

        return handle_huddle_started(
            huddle_event
        )

    # ========================================================
    # UNKNOWN
    # ========================================================

    logger.info(
        "Unknown Huddle event ignored | event=%s",
        event_type
    )

    return None