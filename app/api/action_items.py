from datetime import datetime, timedelta

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.database import meetings_collection

router = APIRouter()


class ActionItemUpdate(BaseModel):
    status: str


# ---------------------------------------------------------
# Convert due_date text into a real date
# ---------------------------------------------------------
def parse_due_date(due_date):
    if not due_date:
        return None

    if not isinstance(due_date, str):
        return None

    value = due_date.strip().lower()

    if value in {
        "",
        "not specified",
        "none",
        "n/a",
        "unknown",
    }:
        return None

    today = datetime.now().date()

    # Today
    if value == "today":
        return today

    # Tomorrow
    if value == "tomorrow":
        return today + timedelta(days=1)

    # Yesterday
    if value == "yesterday":
        return today - timedelta(days=1)

    # -----------------------------------------------------
    # Weekday names
    # -----------------------------------------------------
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

        days_ahead = (target_day - current_day) % 7

        # If it is today, treat it as today.
        return today + timedelta(days=days_ahead)

    # -----------------------------------------------------
    # Try common date formats
    # -----------------------------------------------------
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


# ---------------------------------------------------------
# Determine current status
# ---------------------------------------------------------
def get_action_status(item):
    status = item.get("status", "pending")

    if not isinstance(status, str):
        status = "pending"

    status = status.lower().strip()

    # Completed items must never become overdue
    if status == "completed":
        return "completed"

    due_date = item.get("due_date")

    parsed_date = parse_due_date(due_date)

    if parsed_date and parsed_date < datetime.now().date():
        return "overdue"

    return status


# ---------------------------------------------------------
# GET /action-items
# ---------------------------------------------------------
@router.get("/action-items")
async def get_action_items(
    owner: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    """
    Get action items from all meetings.

    Optional filters:

    /action-items?owner=Sarah

    /action-items?status=pending

    /action-items?status=overdue

    /action-items?owner=Sarah&status=pending
    """

    meetings = meetings_collection.find({})

    action_items = []

    for meeting in meetings:

        meeting_id = str(meeting["_id"])

        meeting_title = meeting.get(
            "meeting_title",
            "Meeting"
        )

        items = meeting.get(
            "action_items",
            []
        )

        for action_index, item in enumerate(items):

            if not isinstance(item, dict):
                continue

            task = item.get(
                "task",
                ""
            )

            item_owner = item.get(
                "owner",
                "Not specified"
            )

            due_date = item.get(
                "due_date",
                "Not specified"
            )

            item_status = get_action_status(item)

            # -----------------------------
            # Owner filter
            # -----------------------------
            if (
                owner
                and item_owner.lower() != owner.lower()
            ):
                continue

            # -----------------------------
            # Status filter
            # -----------------------------
            if (
                status
                and item_status.lower() != status.lower()
            ):
                continue

            action_items.append({
                "task": task,
                "owner": item_owner,
                "due_date": due_date,
                "status": item_status,
                "action_index": action_index,
                "meeting_id": meeting_id,
                "meeting_title": meeting_title
            })

    return {
        "count": len(action_items),
        "action_items": action_items
    }


# ---------------------------------------------------------
# PATCH /action-items/{meeting_id}/{action_index}
# ---------------------------------------------------------
@router.patch("/action-items/{meeting_id}/{action_index}")
async def update_action_item(
    meeting_id: str,
    action_index: int,
    update: ActionItemUpdate,
):
    """
    Update action item status.

    Allowed statuses:

    pending
    in_progress
    completed
    """

    allowed_statuses = {
        "pending",
        "in_progress",
        "completed",
    }

    status = update.status.lower().strip()

    if status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid status. "
                "Use: pending, in_progress, or completed."
            )
        )

    # -----------------------------------------------------
    # Convert meeting ID
    # -----------------------------------------------------
    try:
        object_id = ObjectId(meeting_id)

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid meeting_id."
        )

    # -----------------------------------------------------
    # Find meeting
    # -----------------------------------------------------
    meeting = meetings_collection.find_one({
        "_id": object_id
    })

    if not meeting:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found."
        )

    action_items = meeting.get(
        "action_items",
        []
    )

    # -----------------------------------------------------
    # Validate action index
    # -----------------------------------------------------
    if (
        action_index < 0
        or action_index >= len(action_items)
    ):
        raise HTTPException(
            status_code=404,
            detail="Action item not found."
        )

    # -----------------------------------------------------
    # Validate action item
    # -----------------------------------------------------
    if not isinstance(
        action_items[action_index],
        dict
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid action item format."
        )

    # -----------------------------------------------------
    # Update status
    # -----------------------------------------------------
    action_items[action_index]["status"] = status

    # -----------------------------------------------------
    # Save to MongoDB
    # -----------------------------------------------------
    meetings_collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "action_items": action_items,
                "updated_at": datetime.utcnow()
            }
        }
    )

    return {
        "message": "Action item status updated successfully.",
        "meeting_id": meeting_id,
        "action_index": action_index,
        "action_item": action_items[action_index]
    }
