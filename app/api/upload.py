import os
import shutil

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.transcription import transcribe_audio
from app.services.summarizer import summarize_text

router = APIRouter()

UPLOAD_DIR = "uploads"
TRANSCRIPT_DIR = "transcripts"

ALLOWED_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".m4a",
    ".ogg",   # WhatsApp voice notes
}

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)


@router.post("/upload")
async def upload_audio(file: UploadFile = File(...)):
    # Validate filename
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file name provided."
        )

    # Get file extension
    extension = os.path.splitext(file.filename)[1].lower()

    # Validate extension
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{extension}'. "
                f"Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ),
        )

    # Remove any directory information from filename
    safe_filename = os.path.basename(file.filename)

    # Save uploaded audio
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Generate transcript
    try:
        transcript = transcribe_audio(file_path)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {exc}"
        )

    # Save transcript
    transcript_filename = os.path.splitext(safe_filename)[0] + ".txt"
    transcript_path = os.path.join(TRANSCRIPT_DIR, transcript_filename)

    try:
        with open(transcript_path, "w", encoding="utf-8") as transcript_file:
            transcript_file.write(transcript)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save transcript: {exc}"
        )

    # Generate and save summary
    try:
        summary = summarize_text(transcript)
    except Exception as exc:
        summary = f"Summarization failed: {exc}"

    summary_filename = os.path.splitext(safe_filename)[0] + ".summary.txt"
    summary_path = os.path.join(TRANSCRIPT_DIR, summary_filename)

    try:
        with open(summary_path, "w", encoding="utf-8") as summary_file:
            summary_file.write(summary)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save summary: {exc}"
        )

    return {
        "message": "Audio uploaded, transcribed and summarized successfully.",
        "filename": safe_filename,
        "saved_to": file_path,
        "transcript_file": transcript_path,
        "transcript": transcript,
        "summary_file": summary_path,
        "summary": summary,
    }