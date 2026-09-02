from datetime import datetime, timedelta
import uuid

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.database import meetings_collection


router = APIRouter()


# ============================================================
# PYDANTIC MODEL
# ============================================================

class ActionItemUpdate(BaseModel):
    status: str


# ============================================================
# CONSTANTS
# ============================================================

ALLOWED_STATUSES = {
    "pending",
    "in_progress",
    "completed",
}

FILTER_STATUSES = {
    "pending",
    "in_progress",
    "completed",
    "overdue",
}


# ============================================================
# GENERATE ACTION ID
# ============================================================

def generate_action_id() -> str:
    """
    Generate a unique ID for an action item.
    """

    return uuid.uuid4().hex[:12]


# ============================================================
# PARSE DUE DATE
# ============================================================

def parse_due_date(due_date):
    """
    Convert supported due-date values into a Python date.

    Supported:

        today
        tomorrow
        yesterday
        monday
        tuesday
        ...
        2026-08-26
        26-08-2026
        26/08/2026
        08/26/2026
        August 26, 2026
        Aug 26, 2026
    """

    if not due_date:
        return None

    if not isinstance(due_date, str):
        return None

    value = due_date.strip().lower()

    # --------------------------------------------------------
    # Invalid / unknown values
    # --------------------------------------------------------

    if value in {
        "",
        "not specified",
        "none",
        "n/a",
        "unknown",
    }:
        return None

    today = datetime.now().date()

    # --------------------------------------------------------
    # Relative dates
    # --------------------------------------------------------

    if value == "today":
        return today

    if value == "tomorrow":
        return today + timedelta(days=1)

    if value == "yesterday":
        return today - timedelta(days=1)

    # --------------------------------------------------------
    # Weekdays
    # --------------------------------------------------------

    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    if value in weekdays:

        target_day = weekdays[value]

        current_day = today.weekday()

        days_ahead = (
            target_day - current_day
        ) % 7

        return today + timedelta(
            days=days_ahead
        )

    # --------------------------------------------------------
    # Common date formats
    # --------------------------------------------------------

    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
    ]

    for date_format in formats:

        try:

            return datetime.strptime(
                due_date.strip(),
                date_format
            ).date()

        except ValueError:
            continue

    return None


# ============================================================
# NORMALIZE ACTION ITEM
# ============================================================

def normalize_action_item(item):
    """
    Normalize an action item.

    Important:
    This function modifies the dictionary in memory.
    The caller is responsible for saving changes to MongoDB.
    """

    if not isinstance(item, dict):
        return None

    # --------------------------------------------------------
    # Action ID
    # --------------------------------------------------------

    if not item.get("action_id"):

        item["action_id"] = generate_action_id()

    # --------------------------------------------------------
    # Task
    # --------------------------------------------------------

    if not isinstance(
        item.get("task"),
        str
    ):

        item["task"] = ""

    # --------------------------------------------------------
    # Owner
    # --------------------------------------------------------

    if not isinstance(
        item.get("owner"),
        str
    ):

        item["owner"] = "Not specified"

    item["owner"] = (
        item["owner"].strip()
        or "Not specified"
    )

    # --------------------------------------------------------
    # Due date
    # --------------------------------------------------------

    if not isinstance(
        item.get("due_date"),
        str
    ):

        item["due_date"] = "Not specified"

    item["due_date"] = (
        item["due_date"].strip()
        or "Not specified"
    )

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    if not isinstance(
        item.get("status"),
        str
    ):

        item["status"] = "pending"

    item["status"] = (
        item["status"]
        .lower()
        .strip()
    )

    if item["status"] not in ALLOWED_STATUSES:

        item["status"] = "pending"

    return item


# ============================================================
# ENSURE ACTION IDS ARE STORED
# ============================================================

def ensure_action_ids(meeting):
    """
    Make sure all action items have stable action IDs.

    This fixes old meetings that were created before
    action_id was introduced.
    """

    action_items = meeting.get(
        "action_items",
        []
    )

    if not isinstance(
        action_items,
        list
    ):

        return []

    changed = False

    normalized_items = []

    for item in action_items:

        had_action_id = bool(
            isinstance(item, dict) and item.get("action_id")
        )

        normalized = normalize_action_item(
            item
        )

        if not normalized:
            continue

        normalized_items.append(
            normalized
        )

        if not had_action_id:
            changed = True

    # --------------------------------------------------------
    # Save generated IDs to MongoDB
    # --------------------------------------------------------

    if changed:

        meetings_collection.update_one(

            {
                "_id": meeting["_id"]
            },

            {
                "$set": {
                    "action_items":
                        normalized_items,

                    "updated_at":
                        datetime.utcnow()
                }
            }
        )

    return normalized_items


# ============================================================
# GET EFFECTIVE ACTION STATUS
# ============================================================

def get_action_status(item) -> str:
    """
    Determine the current status.

    Stored status:

        pending
        in_progress
        completed

    Computed status:

        overdue

    We do NOT permanently store "overdue".
    """

    status = item.get(
        "status",
        "pending"
    )

    if not isinstance(
        status,
        str
    ):

        status = "pending"

    status = (
        status
        .lower()
        .strip()
    )

    # --------------------------------------------------------
    # Completed items never become overdue
    # --------------------------------------------------------

    if status == "completed":

        return "completed"

    # --------------------------------------------------------
    # Check due date
    # --------------------------------------------------------

    due_date = item.get(
        "due_date"
    )

    parsed_date = parse_due_date(
        due_date
    )

    if (
        parsed_date
        and parsed_date < datetime.now().date()
    ):

        return "overdue"

    return status


# ============================================================
# BUILD ACTION ITEM RESPONSE
# ============================================================

def build_action_item_response(
    meeting,
    item,
    action_index
):
    """
    Build a consistent API response for an action item.
    """

    return {

        "action_id":
            item.get(
                "action_id"
            ),

        "task":
            item.get(
                "task",
                ""
            ),

        "owner":
            item.get(
                "owner",
                "Not specified"
            ),

        "due_date":
            item.get(
                "due_date",
                "Not specified"
            ),

        # Effective status
        "status":
            get_action_status(
                item
            ),

        # Actual status stored in DB
        "stored_status":
            item.get(
                "status",
                "pending"
            ),

        "action_index":
            action_index,

        "meeting_id":
            str(
                meeting["_id"]
            ),

        "meeting_title":
            meeting.get(
                "meeting_title",
                "Meeting"
            ),

        "created_at":
            meeting.get(
                "uploaded_at"
            ),

        "updated_at":
            item.get(
                "updated_at"
            ),

        "completed_at":
            item.get(
                "completed_at"
            )
    }


# ============================================================
# GET ALL ACTION ITEMS
# ============================================================

@router.get("/action-items")
async def get_action_items(

    owner: str | None = Query(
        default=None
    ),

    status: str | None = Query(
        default=None
    ),
):
    """
    Get action items from all meetings.

    Examples:

        GET /action-items

        GET /action-items?owner=Ali

        GET /action-items?status=pending

        GET /action-items?status=in_progress

        GET /action-items?status=completed

        GET /action-items?status=overdue

        GET /action-items?owner=Ali&status=pending
    """

    # --------------------------------------------------------
    # Validate status filter
    # --------------------------------------------------------

    requested_status = None

    if status:

        requested_status = (
            status
            .lower()
            .strip()
        )

        if requested_status not in FILTER_STATUSES:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid status filter. "
                    "Use: pending, in_progress, "
                    "completed, or overdue."
                )
            )

    # --------------------------------------------------------
    # Normalize owner filter
    # --------------------------------------------------------

    requested_owner = None

    if isinstance(
        owner,
        str
    ):

        requested_owner = (
            owner
            .strip()
            .lower()
        )

    # --------------------------------------------------------
    # Get meetings
    # --------------------------------------------------------

    meetings = meetings_collection.find({})

    action_items = []

    for meeting in meetings:

        items = ensure_action_ids(
            meeting
        )

        # ----------------------------------------------------
        # Process action items
        # ----------------------------------------------------

        for action_index, item in enumerate(
            items
        ):

            item_status = get_action_status(
                item
            )

            item_owner = item.get(
                "owner",
                "Not specified"
            )

            # ------------------------------------------------
            # Owner filter
            # ------------------------------------------------

            if requested_owner:

                if (
                    item_owner
                    .strip()
                    .lower()
                    != requested_owner
                ):

                    continue

            # ------------------------------------------------
            # Status filter
            # ------------------------------------------------

            if (
                requested_status
                and item_status
                != requested_status
            ):

                continue

            action_items.append(
                build_action_item_response(
                    meeting,
                    item,
                    action_index
                )
            )

    return {

        "count":
            len(action_items),

        "action_items":
            action_items
    }


# ============================================================
# GET OVERDUE ACTION ITEMS
# ============================================================

@router.get("/action-items/overdue")
async def get_overdue_action_items():
    """
    Return all action items whose due date has passed
    and which are not completed.
    """

    meetings = meetings_collection.find({})

    overdue_items = []

    for meeting in meetings:

        items = ensure_action_ids(
            meeting
        )

        for action_index, item in enumerate(
            items
        ):

            status = get_action_status(
                item
            )

            if status != "overdue":
                continue

            overdue_items.append(
                build_action_item_response(
                    meeting,
                    item,
                    action_index
                )
            )

    return {

        "count":
            len(overdue_items),

        "action_items":
            overdue_items
    }


# ============================================================
# GET PENDING ACTION ITEMS
# ============================================================

@router.get("/action-items/pending")
async def get_pending_action_items():
    """
    Return pending and in-progress action items.

    Overdue items are excluded.
    """

    meetings = meetings_collection.find({})

    pending_items = []

    for meeting in meetings:

        items = ensure_action_ids(
            meeting
        )

        for action_index, item in enumerate(
            items
        ):

            status = get_action_status(
                item
            )

            if status not in {
                "pending",
                "in_progress"
            }:

                continue

            pending_items.append(
                build_action_item_response(
                    meeting,
                    item,
                    action_index
                )
            )

    return {

        "count":
            len(pending_items),

        "action_items":
            pending_items
    }


# ============================================================
# UPDATE ACTION ITEM
# ============================================================

@router.patch(
    "/action-items/{meeting_id}/{action_id}"
)
async def update_action_item(

    meeting_id: str,

    action_id: str,

    update: ActionItemUpdate,
):
    """
    Update an action item using its stable action_id.

    Allowed stored statuses:

        pending
        in_progress
        completed

    "overdue" cannot be manually assigned.
    It is automatically calculated from due_date.
    """

    # --------------------------------------------------------
    # Validate status
    # --------------------------------------------------------

    if not isinstance(
        update.status,
        str
    ):

        raise HTTPException(
            status_code=400,
            detail="Status must be a string."
        )

    status = (
        update.status
        .lower()
        .strip()
    )

    if status not in ALLOWED_STATUSES:

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid status. "
                "Use: pending, in_progress, "
                "or completed."
            )
        )

    # --------------------------------------------------------
    # Validate meeting ID
    # --------------------------------------------------------

    try:

        object_id = ObjectId(
            meeting_id
        )

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Invalid meeting_id."
        )

    # --------------------------------------------------------
    # Find meeting
    # --------------------------------------------------------

    meeting = meetings_collection.find_one({
        "_id": object_id
    })

    if not meeting:

        raise HTTPException(
            status_code=404,
            detail="Meeting not found."
        )

    # --------------------------------------------------------
    # Get action items
    # --------------------------------------------------------

    action_items = meeting.get(
        "action_items",
        []
    )

    if not isinstance(
        action_items,
        list
    ):

        raise HTTPException(
            status_code=400,
            detail="Invalid action_items format."
        )

    # --------------------------------------------------------
    # Find action item
    # --------------------------------------------------------

    target_item = None
    target_index = None

    for index, raw_item in enumerate(
        action_items
    ):

        if not isinstance(
            raw_item,
            dict
        ):

            continue

        # ----------------------------------------------------
        # Backward compatibility
        # ----------------------------------------------------

        if not raw_item.get(
            "action_id"
        ):

            raw_item["action_id"] = (
                generate_action_id()
            )

        # ----------------------------------------------------
        # Match action ID
        # ----------------------------------------------------

        if (
            raw_item.get(
                "action_id"
            )
            == action_id
        ):

            target_item = raw_item
            target_index = index

            break

    # --------------------------------------------------------
    # Action not found
    # --------------------------------------------------------

    if target_item is None:

        raise HTTPException(
            status_code=404,
            detail="Action item not found."
        )

    # --------------------------------------------------------
    # Update status
    # --------------------------------------------------------

    target_item["status"] = status

    target_item["updated_at"] = (
        datetime.utcnow()
    )

    # --------------------------------------------------------
    # Completion timestamp
    # --------------------------------------------------------

    if status == "completed":

        target_item["completed_at"] = (
            datetime.utcnow()
        )

    else:

        target_item.pop(
            "completed_at",
            None
        )

    # --------------------------------------------------------
    # Save MongoDB
    # --------------------------------------------------------

    meetings_collection.update_one(

        {
            "_id": object_id
        },

        {
            "$set": {

                "action_items":
                    action_items,

                "updated_at":
                    datetime.utcnow()
            }
        }
    )

    # --------------------------------------------------------
    # Effective status after update
    # --------------------------------------------------------

    effective_status = get_action_status(
        target_item
    )

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return {

        "message":
            "Action item status updated successfully.",

        "meeting_id":
            meeting_id,

        "action_id":
            action_id,

        "action_index":
            target_index,

        "action_item": {

            "action_id":
                target_item.get(
                    "action_id"
                ),

            "task":
                target_item.get(
                    "task",
                    ""
                ),

            "owner":
                target_item.get(
                    "owner",
                    "Not specified"
                ),

            "due_date":
                target_item.get(
                    "due_date",
                    "Not specified"
                ),

            "status":
                effective_status,

            "stored_status":
                target_item.get(
                    "status",
                    "pending"
                ),

            "updated_at":
                target_item.get(
                    "updated_at"
                ),

            "completed_at":
                target_item.get(
                    "completed_at"
                )
        }
    }