import os
import shutil
import json
import uuid
import re
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.database import meetings_collection
from app.services.transcription import transcribe_audio
from app.services.summarizer import summarize_text
from app.services.slack import send_meeting_summary
from app.services.jira import create_jira_issues
from app.services.embedding import create_meeting_embedding


router = APIRouter()


# ============================================================
# DIRECTORIES
# ============================================================

UPLOAD_DIR = "uploads"
TRANSCRIPT_DIR = "transcripts"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)


# ============================================================
# ALLOWED AUDIO FILES
# ============================================================

ALLOWED_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".m4a",
    ".ogg",
}


# ============================================================
# EXTRACT SPEAKERS FROM TRANSCRIPT
# ============================================================

def extract_speakers(transcript: str) -> list:
    """
    Extract unique speaker labels from the diarized transcript.

    Example transcript:

    [00:00 - 00:04] SPEAKER_01
    Hello...

    [00:04 - 00:09] SPEAKER_00
    Hi...

    Returns:

    [
        "SPEAKER_01",
        "SPEAKER_00"
    ]
    """

    speakers = []

    pattern = r"\]\s+(SPEAKER_\d+)"

    matches = re.findall(
        pattern,
        transcript
    )

    for speaker in matches:

        if speaker not in speakers:
            speakers.append(speaker)

    return speakers


# ============================================================
# UPLOAD ENDPOINT
# ============================================================

@router.post("/upload")
async def upload_audio(
    file: UploadFile = File(...)
):

    # ========================================================
    # 1. VALIDATE FILE
    # ========================================================

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="No file name provided"
        )


    extension = os.path.splitext(
        file.filename
    )[1].lower()


    if extension not in ALLOWED_EXTENSIONS:

        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {extension}"
        )


    # ========================================================
    # 2. CREATE UNIQUE FILE NAME
    # ========================================================

    unique_name = (
        f"{uuid.uuid4().hex}_"
        f"{os.path.basename(file.filename)}"
    )


    file_path = os.path.join(
        UPLOAD_DIR,
        unique_name
    )


    # ========================================================
    # 3. SAVE AUDIO FILE
    # ========================================================

    try:

        with open(
            file_path,
            "wb"
        ) as buffer:

            shutil.copyfileobj(
                file.file,
                buffer
            )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to save audio file: {e}"
        )


    # ========================================================
    # 4. TRANSCRIPTION + SPEAKER DIARIZATION
    # ========================================================

    print("\n========================================")
    print("Starting transcription...")
    print("========================================")


    try:

        transcript = transcribe_audio(
            file_path
        )

    except Exception as e:

        print(
            "❌ Transcription error:",
            e
        )

        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {e}"
        )


    print(
        "✅ Transcription completed"
    )


    # ========================================================
    # 4.1 EXTRACT SPEAKERS
    # ========================================================

    speakers = extract_speakers(
        transcript
    )


    speaker_count = len(
        speakers
    )


    print(
        "Detected speakers:",
        speakers
    )


    print(
        "Speaker count:",
        speaker_count
    )


    # ========================================================
    # 5. SAVE TRANSCRIPT
    # ========================================================

    transcript_path = os.path.join(
        TRANSCRIPT_DIR,
        unique_name + ".txt"
    )


    try:

        with open(
            transcript_path,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(transcript)

    except Exception as e:

        print(
            "Transcript file error:",
            e
        )


    # ========================================================
    # 6. LLM MEETING ANALYSIS
    # ========================================================

    print(
        "\nGenerating meeting analysis..."
    )


    try:

        summary_data = summarize_text(
            transcript
        )

    except Exception as e:

        print(
            "LLM Error:",
            e
        )

        summary_data = {}


    # ========================================================
    # 7. VALIDATE SUMMARY DATA
    # ========================================================

    if not isinstance(
        summary_data,
        dict
    ):

        summary_data = {}


    summary_data.setdefault(
        "meeting_title",
        "Meeting"
    )

    summary_data.setdefault(
        "summary",
        ""
    )

    summary_data.setdefault(
        "topics",
        []
    )

    summary_data.setdefault(
        "decisions",
        []
    )

    summary_data.setdefault(
        "open_questions",
        []
    )

    summary_data.setdefault(
        "key_points",
        []
    )

    summary_data.setdefault(
        "action_items",
        []
    )


    # ========================================================
    # 8. EXTRACT MEETING DATA
    # ========================================================

    meeting_title = summary_data.get(
        "meeting_title",
        "Meeting"
    )


    summary = summary_data.get(
        "summary",
        ""
    )


    topics = summary_data.get(
        "topics",
        []
    )


    decisions = summary_data.get(
        "decisions",
        []
    )


    open_questions = summary_data.get(
        "open_questions",
        []
    )


    key_points = summary_data.get(
        "key_points",
        []
    )


    action_items = summary_data.get(
        "action_items",
        []
    )
    # ========================================================
    # NORMALIZE ACTION ITEMS
    # ========================================================

    normalized_action_items = []

    for item in action_items:

        if not isinstance(item, dict):
            continue

        item["action_id"] = (
            item.get("action_id")
            or uuid.uuid4().hex[:12]
        )

        item.setdefault(
            "task",
            ""
        )

        item.setdefault(
            "owner",
            "Not specified"
        )

        item.setdefault(
            "due_date",
            "Not specified"
        )

        item.setdefault(
            "status",
            "pending"
        )

        normalized_action_items.append(item)


    action_items = normalized_action_items
    # ========================================================
    # ADD STABLE IDs TO ACTION ITEMS
    # ========================================================

    normalized_action_items = []

    for item in action_items:

        if not isinstance(item, dict):
         continue

        item["action_id"] = item.get(
        "action_id",
            uuid.uuid4().hex[:8]
        )

        item.setdefault(
            "task",
            ""
        )

        item.setdefault(
            "owner",
            "Not specified"
        )

        item.setdefault(
            "due_date",
            "Not specified"
        )

        item.setdefault(
            "status",
            "pending"
        )

        normalized_action_items.append(item)


    action_items = normalized_action_items  

    # ========================================================
    # 9. SAVE SUMMARY JSON
    # ========================================================

    summary_path = os.path.join(
        TRANSCRIPT_DIR,
        unique_name + ".summary.json"
    )


    try:

        with open(
            summary_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                summary_data,
                f,
                indent=4,
                ensure_ascii=False
            )

    except Exception as e:

        print(
            "Summary file error:",
            e
        )


    # ========================================================
    # 10. SAVE ACTION ITEMS
    # ========================================================

    action_path = os.path.join(
        TRANSCRIPT_DIR,
        unique_name + ".actions.json"
    )


    try:

        with open(
            action_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                action_items,
                f,
                indent=4,
                ensure_ascii=False
            )

    except Exception as e:

        print(
            "Action items file error:",
            e
        )


    # ========================================================
    # 11. CREATE EMBEDDING
    # ========================================================

    print(
        "\nGenerating embedding..."
    )


    embedding = []


    try:

        embedding = create_meeting_embedding(

            meeting_title=meeting_title,

            summary=summary,

            topics=topics,

            decisions=decisions,

            open_questions=open_questions,

            key_points=key_points,

            action_items=action_items
        )


        # ----------------------------------------------------
        # VERIFY EMBEDDING
        # ----------------------------------------------------

        if len(embedding) != 384:

            raise ValueError(
                f"Invalid embedding length: {len(embedding)}"
            )


        print(
            "✅ Embedding generated successfully."
        )


        print(
            f"Embedding length: {len(embedding)}"
        )


    except Exception as e:

        print(
            "❌ Embedding Error:",
            e
        )

        embedding = []


    # ========================================================
    # 12. CREATE MONGODB DOCUMENT
    # ========================================================

    meeting_document = {

        "filename":
            unique_name,

        "uploaded_at":
            datetime.utcnow(),

        # ----------------------------------------------------
        # SPEAKER INFORMATION
        # ----------------------------------------------------

        "speakers":
            speakers,

        "speaker_count":
            speaker_count,

        # ----------------------------------------------------
        # TRANSCRIPT
        # ----------------------------------------------------

        "transcript":
            transcript,

        # ----------------------------------------------------
        # MEETING ANALYSIS
        # ----------------------------------------------------

        "meeting_title":
            meeting_title,

        "summary":
            summary,

        "topics":
            topics,

        "decisions":
            decisions,

        "open_questions":
            open_questions,

        "key_points":
            key_points,

        "action_items":
            action_items,

        # ----------------------------------------------------
        # EMBEDDING
        # ----------------------------------------------------

        "embedding":
            embedding
    }


    # ========================================================
    # 13. SAVE TO MONGODB
    # ========================================================

    print(
        "\nSaving meeting to MongoDB..."
    )


    try:

        result = meetings_collection.insert_one(
            meeting_document
        )


        print(
            "✅ Meeting saved to MongoDB."
        )


        print(
            f"Meeting ID: {result.inserted_id}"
        )


    except Exception as e:

        print(
            "❌ MongoDB Error:",
            e
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to save meeting to database: "
                f"{e}"
            )
        )


    # ========================================================
    # 14. SEND SLACK NOTIFICATION
    # ========================================================

    try:

        print(
            "\nSending Slack notification..."
        )


        send_meeting_summary(

            meeting_title=meeting_title,

            summary=summary,

            key_points=key_points,

            decisions=decisions,

            open_questions=open_questions,

            action_items=action_items,

            filename=unique_name
        )


        print(
            "✅ Slack notification sent"
        )


    except Exception as e:

        # Slack failure should NOT delete the meeting

        print(
            "Slack Error:",
            e
        )


    # ========================================================
    # 15. CREATE JIRA ISSUES
    # ========================================================

    try:

        print(
            "\nCreating Jira issues..."
        )


        if action_items:

            create_jira_issues(
                action_items
            )

        else:

            print(
                "No action items. Skipping Jira."
            )


    except Exception as e:

        # Jira failure should NOT delete the meeting

        print(
            "Jira Error:",
            e
        )


    # ========================================================
    # 16. RETURN RESPONSE
    # ========================================================

    print(
        "\n========================================"
    )

    print(
        "✅ MEETING PROCESSING COMPLETED"
    )

    print(
        "========================================"
    )


    return {

        "message":
            "Meeting processed successfully.",

        "meeting_id":
            str(result.inserted_id),

        "filename":
            unique_name,

        # ----------------------------------------------------
        # SPEAKER INFORMATION
        # ----------------------------------------------------

        "speakers":
            speakers,

        "speaker_count":
            speaker_count,

        # ----------------------------------------------------
        # TRANSCRIPT
        # ----------------------------------------------------

        "transcript":
            transcript,

        # ----------------------------------------------------
        # MEETING ANALYSIS
        # ----------------------------------------------------

        "meeting_title":
            meeting_title,

        "summary":
            summary,

        "topics":
            topics,

        "decisions":
            decisions,

        "open_questions":
            open_questions,

        "key_points":
            key_points,

        "action_items":
            action_items
    }