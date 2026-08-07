import os
import shutil
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.database import meetings_collection
from app.services.transcription import transcribe_audio
from app.services.summarizer import summarize_text
from app.services.slack import send_meeting_summary
from app.services.jira import create_jira_issues
from app.services.embedding import create_meeting_embedding

router = APIRouter()

UPLOAD_DIR = "uploads"
TRANSCRIPT_DIR = "transcripts"

ALLOWED_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".m4a",
    ".ogg",
}

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)


@router.post("/upload")
async def upload_audio(
    file: UploadFile = File(...)
):

    # -----------------------------
    # Validate file
    # -----------------------------

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file name provided"
        )

    extension = os.path.splitext(file.filename)[1].lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {extension}"
        )

    unique_name = (
        f"{uuid.uuid4().hex}_"
        f"{os.path.basename(file.filename)}"
    )

    file_path = os.path.join(
        UPLOAD_DIR,
        unique_name
    )

    # -----------------------------
    # Save Audio
    # -----------------------------

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # -----------------------------
    # Whisper Transcription
    # -----------------------------

    print("Starting transcription...")

    transcript = transcribe_audio(file_path)

    print("Transcription completed")

    transcript_path = os.path.join(
        TRANSCRIPT_DIR,
        unique_name + ".txt"
    )

    with open(
        transcript_path,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(transcript)

    # -----------------------------
    # LLM Analysis
    # -----------------------------

    print("Generating meeting analysis...")

    summary_data = summarize_text(transcript)

    if not isinstance(summary_data, dict):
        summary_data = {
            "meeting_title": "Meeting",
            "summary": str(summary_data),
            "topics": [],
            "decisions": [],
            "open_questions": [],
            "key_points": [],
            "action_items": []
        }

    action_items = summary_data.get(
        "action_items",
        []
    )

    summary_path = os.path.join(
        TRANSCRIPT_DIR,
        unique_name + ".summary.json"
    )

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

    action_path = os.path.join(
        TRANSCRIPT_DIR,
        unique_name + ".actions.json"
    )

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

    # -----------------------------
    # Generate Embedding
    # -----------------------------

    print("Generating embedding...")

    embedding = create_meeting_embedding(
        meeting_title=summary_data.get(
            "meeting_title",
            ""
        ),
        summary=summary_data.get(
            "summary",
            ""
        ),
        topics=summary_data.get(
            "topics",
            []
        ),
        decisions=summary_data.get(
            "decisions",
            []
        )
    )

    print("Embedding generated.")

    # -----------------------------
    # MongoDB
    # -----------------------------

    meeting_document = {

        "filename": unique_name,

        "uploaded_at": datetime.utcnow(),

        "transcript": transcript,

        "meeting_title": summary_data.get(
            "meeting_title",
            ""
        ),

        "summary": summary_data.get(
            "summary",
            ""
        ),

        "topics": summary_data.get(
            "topics",
            []
        ),

        "decisions": summary_data.get(
            "decisions",
            []
        ),

        "open_questions": summary_data.get(
            "open_questions",
            []
        ),

        "key_points": summary_data.get(
            "key_points",
            []
        ),

        "action_items": action_items,

        "embedding": embedding

    }

    result = meetings_collection.insert_one(
        meeting_document
    )

    # -----------------------------
    # Slack
    # -----------------------------

    try:

        send_meeting_summary(

            meeting_title=summary_data.get(
                "meeting_title",
                ""
            ),

            summary=summary_data.get(
                "summary",
                ""
            ),

            action_items=action_items,

            filename=unique_name

        )

    except Exception as e:

        print(
            "Slack Error:",
            e
        )

    # -----------------------------
    # Jira
    # -----------------------------

    try:

        print(
            "Creating Jira issues..."
        )

        create_jira_issues(
            action_items
        )

    except Exception as e:

        print(
            "Jira Error:",
            e
        )

    return {

        "message":
            "Meeting processed successfully.",

        "meeting_id":
            str(result.inserted_id),

        "filename":
            unique_name,

        "transcript":
            transcript,

        "meeting_title":
            summary_data.get(
                "meeting_title",
                ""
            ),

        "summary":
            summary_data.get(
                "summary",
                ""
            ),

        "topics":
            summary_data.get(
                "topics",
                []
            ),

        "decisions":
            summary_data.get(
                "decisions",
                []
            ),

        "open_questions":
            summary_data.get(
                "open_questions",
                []
            ),

        "key_points":
            summary_data.get(
                "key_points",
                []
            ),

        "action_items":
            action_items

    }