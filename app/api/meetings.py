from fastapi import APIRouter, HTTPException
from bson import ObjectId

from app.database import meetings_collection

router = APIRouter()


# ============================================================
# GET ALL MEETINGS
# ============================================================

@router.get("/meetings")
async def get_meetings():
    """
    Get all meetings.

    Transcript and embedding are excluded from the list
    to keep the response smaller.
    """

    meetings = list(
        meetings_collection.find(
            {},
            {
                "embedding": 0,
                "transcript": 0
            }
        )
    )

    for meeting in meetings:
        meeting["_id"] = str(meeting["_id"])

    return {
        "count": len(meetings),
        "meetings": meetings
    }


# ============================================================
# GET SINGLE MEETING
# ============================================================

@router.get("/meetings/{meeting_id}")
async def get_meeting(meeting_id: str):
    """
    Get complete details of one meeting.
    """

    # Validate MongoDB ObjectId
    try:
        object_id = ObjectId(meeting_id)

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid meeting_id."
        )

    # Find meeting
    meeting = meetings_collection.find_one(
        {"_id": object_id},
        {
            "embedding": 0
        }
    )

    # Meeting doesn't exist
    if not meeting:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found."
        )

    # Convert ObjectId to string
    meeting["_id"] = str(meeting["_id"])

    return meeting