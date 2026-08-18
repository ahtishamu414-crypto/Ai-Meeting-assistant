# ============================================================
# app/services/zoom_recording_watcher.py
# ============================================================

import os
import time
import json
import hashlib
import threading

from pathlib import Path
from datetime import datetime, timezone

from app.services.transcription import transcribe_audio
from app.services.summarizer import summarize_text
from app.database import meetings_collection

# Zoom Team Chat
from app.services.zoom_chat import (
    get_or_create_zoom_channel,
    send_meeting_summary_to_zoom,
)


# ============================================================
# CONFIGURATION
# ============================================================

ZOOM_RECORDING_DIR = Path(
    os.getenv(
        "ZOOM_RECORDING_DIR",
        r"C:\Users\BN Com\Documents\Zoom",
    )
)

AUDIO_EXTENSIONS = {
    ".m4a",
    ".mp3",
    ".wav",
    ".ogg",
    ".flac",
}

CHECK_INTERVAL = 5

FILE_STABLE_CHECKS = 3

FILE_STABLE_INTERVAL = 3

DEFAULT_CHAT_CHANNEL = "AI Meeting Assistant"


# ============================================================
# STATE
# ============================================================

processed_files = set()

processing_files = set()

watcher_thread = None

watcher_running = False

processing_lock = threading.Lock()


# ============================================================
# ENVIRONMENT HELPER
# ============================================================

def get_env(
    name: str,
    default: str | None = None,
):
    """
    Safely read an environment variable.
    """

    value = os.getenv(name)

    if value is None:
        return default

    value = value.strip()

    if not value:
        return default

    return value


# ============================================================
# LOGGING
# ============================================================

def log(message: str):
    """
    Print watcher messages with timestamp.
    """

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    print(
        f"[ZOOM WATCHER {timestamp}] {message}"
    )


# ============================================================
# UTC TIMESTAMP
# ============================================================

def utc_now():
    """
    Return current UTC datetime.
    """

    return datetime.now(timezone.utc)


# ============================================================
# RECORDING ID
# ============================================================

def generate_recording_id(
    file_path: Path,
) -> str:
    """
    Generate a stable unique ID for a local recording.

    Uses:
        - absolute file path
        - file size
        - modification time
    """

    try:

        stat = file_path.stat()

        raw_value = (
            f"{file_path.resolve()}|"
            f"{stat.st_size}|"
            f"{stat.st_mtime}"
        )

    except OSError:

        raw_value = str(
            file_path.resolve()
        )

    return hashlib.sha256(
        raw_value.encode("utf-8")
    ).hexdigest()


# ============================================================
# PROCESSED MARKER
# ============================================================

def get_processed_marker(
    file_path: Path,
) -> Path:
    """
    Return persistent processed marker.

    Example:

        meeting.m4a
        meeting.processed
    """

    return file_path.with_suffix(
        ".processed"
    )


def is_already_processed(
    file_path: Path,
) -> bool:

    file_key = str(
        file_path.resolve()
    )

    # --------------------------------------------------------
    # Memory check
    # --------------------------------------------------------

    if file_key in processed_files:

        return True

    # --------------------------------------------------------
    # Persistent marker check
    # --------------------------------------------------------

    marker_path = get_processed_marker(
        file_path
    )

    if marker_path.exists():

        processed_files.add(
            file_key
        )

        return True

    return False


def mark_as_processed(
    file_path: Path,
) -> bool:

    marker_path = get_processed_marker(
        file_path
    )

    try:

        marker_data = {

            "processed":
                True,

            "file":
                str(
                    file_path.resolve()
                ),

            "processed_at":
                utc_now().isoformat(),
        }

        with open(
            marker_path,
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                marker_data,
                f,
                indent=4,
                ensure_ascii=False,
            )

        file_key = str(
            file_path.resolve()
        )

        processed_files.add(
            file_key
        )

        log(
            f"Processed marker created: "
            f"{marker_path.name}"
        )

        return True

    except Exception as e:

        log(
            f"Failed to create processed marker: {e}"
        )

        return False


# ============================================================
# FIND AUDIO FILES
# ============================================================

def find_audio_files():

    if not ZOOM_RECORDING_DIR.exists():

        return []

    audio_files = []

    try:

        for path in ZOOM_RECORDING_DIR.rglob("*"):

            if not path.is_file():
                continue

            if path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue

            # Ignore generated files
            if path.name.endswith(
                ".transcript.txt"
            ):
                continue

            if path.name.endswith(
                ".summary.json"
            ):
                continue

            # Ignore processed marker files
            if path.name.endswith(
                ".processed"
            ):
                continue

            audio_files.append(path)

    except Exception as e:

        log(
            f"Error scanning Zoom directory: {e}"
        )

    return audio_files


# ============================================================
# FILE STABILITY
# ============================================================

def wait_until_file_is_stable(
    file_path: Path,
    checks: int = FILE_STABLE_CHECKS,
    interval: int = FILE_STABLE_INTERVAL,
) -> bool:

    if not file_path.exists():

        return False

    log(
        f"Waiting for recording to finish: "
        f"{file_path.name}"
    )

    previous_size = -1

    stable_count = 0

    max_attempts = checks * 10

    for _ in range(max_attempts):

        if not file_path.exists():

            return False

        try:

            current_size = (
                file_path.stat().st_size
            )

        except OSError:

            time.sleep(interval)

            continue

        if current_size == previous_size:

            stable_count += 1

            log(
                f"File stable check "
                f"{stable_count}/{checks}"
            )

            if stable_count >= checks:

                log(
                    f"Recording file is stable: "
                    f"{file_path.name}"
                )

                return True

        else:

            stable_count = 0

            log(
                f"Recording still changing: "
                f"{current_size / (1024 * 1024):.2f} MB"
            )

        previous_size = current_size

        time.sleep(interval)

    log(
        f"Recording did not become stable: "
        f"{file_path.name}"
    )

    return False


# ============================================================
# BUILD MONGODB DOCUMENT
# ============================================================

def build_meeting_document(
    file_path: Path,
    transcript: str,
    summary_data: dict,
):
    """
    Build complete MongoDB meeting document.
    """

    # --------------------------------------------------------
    # File information
    # --------------------------------------------------------

    try:

        file_stat = file_path.stat()

        file_size_bytes = (
            file_stat.st_size
        )

        file_size_mb = round(
            file_size_bytes /
            (1024 * 1024),
            2,
        )

    except OSError:

        file_size_bytes = None

        file_size_mb = None

    recording_id = (
        generate_recording_id(
            file_path
        )
    )

    # --------------------------------------------------------
    # Summary information
    # --------------------------------------------------------

    meeting_title = summary_data.get(
        "meeting_title",
        "Zoom Meeting",
    )

    summary = summary_data.get(
        "summary",
        "",
    )

    topics = summary_data.get(
        "topics",
        [],
    )

    decisions = summary_data.get(
        "decisions",
        [],
    )

    open_questions = summary_data.get(
        "open_questions",
        [],
    )

    key_points = summary_data.get(
        "key_points",
        [],
    )

    action_items = summary_data.get(
        "action_items",
        [],
    )

    # --------------------------------------------------------
    # MongoDB document
    # --------------------------------------------------------

    meeting_document = {

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

        "transcript":
            transcript,

        "recording": {

            "recording_id":
                recording_id,

            "filename":
                file_path.name,

            "path":
                str(
                    file_path.resolve()
                ),

            "directory":
                str(
                    file_path.parent.resolve()
                ),

            "extension":
                file_path.suffix.lower(),

            "size_bytes":
                file_size_bytes,

            "size_mb":
                file_size_mb,
        },

        "source":
            "zoom_local_recording",

        "processing": {

            "status":
                "completed",

            "processed_at":
                utc_now(),

            "pipeline": [

                "local_zoom_recording",

                "file_stability_check",

                "whisper_transcription",

                "ollama_summary",

                "mongodb_storage",

                "zoom_team_chat",
            ],
        },

        "created_at":
            utc_now(),

        "zoom": {

            "meeting_id":
                None,

            "meeting_uuid":
                None,

            "event_type":
                None,

            "participants":
                [],
        },
    }

    return meeting_document


# ============================================================
# SAVE MEETING TO MONGODB
# ============================================================

def save_meeting_to_mongodb(
    file_path: Path,
    transcript: str,
    summary_data: dict,
) -> bool:

    try:

        meeting_document = (
            build_meeting_document(
                file_path=file_path,
                transcript=transcript,
                summary_data=summary_data,
            )
        )

        result = (
            meetings_collection.insert_one(
                meeting_document
            )
        )

        log(
            "Meeting successfully saved to MongoDB."
        )

        log(
            f"MongoDB Meeting ID: "
            f"{result.inserted_id}"
        )

        log(
            "MongoDB data saved:"
        )

        log(
            f"  Title: "
            f"{meeting_document['meeting_title']}"
        )

        log(
            f"  Summary: "
            f"{bool(meeting_document['summary'])}"
        )

        log(
            f"  Topics: "
            f"{len(meeting_document['topics'])}"
        )

        log(
            f"  Decisions: "
            f"{len(meeting_document['decisions'])}"
        )

        log(
            f"  Open questions: "
            f"{len(meeting_document['open_questions'])}"
        )

        log(
            f"  Key points: "
            f"{len(meeting_document['key_points'])}"
        )

        log(
            f"  Action items: "
            f"{len(meeting_document['action_items'])}"
        )

        log(
            f"  Transcript characters: "
            f"{len(meeting_document['transcript'])}"
        )

        log(
            f"  Recording: "
            f"{meeting_document['recording']['filename']}"
        )

        log(
            f"  Recording size: "
            f"{meeting_document['recording']['size_mb']} MB"
        )

        log(
            f"  Source: "
            f"{meeting_document['source']}"
        )

        return True

    except Exception as e:

        log(
            f"MongoDB save failed: {e}"
        )

        return False


# ============================================================
# SEND SUMMARY TO ZOOM TEAM CHAT
# ============================================================

def send_summary_to_zoom_chat(
    file_path: Path,
    summary_data: dict,
) -> bool:
    """
    Send the generated meeting summary to Zoom Team Chat.

    If ZOOM_CHAT_CHANNEL is not configured,
    automatically find/create:

        AI Meeting Assistant
    """

    try:

        meeting_title = summary_data.get(
            "meeting_title",
            "Zoom Meeting",
        )

        summary = summary_data.get(
            "summary",
            "",
        )

        key_points = summary_data.get(
            "key_points",
            [],
        )

        decisions = summary_data.get(
            "decisions",
            [],
        )

        open_questions = summary_data.get(
            "open_questions",
            [],
        )

        action_items = summary_data.get(
            "action_items",
            [],
        )

        # ====================================================
        # GET CHANNEL
        # ====================================================

        channel_id = get_env(
            "ZOOM_CHAT_CHANNEL"
        )

        if not channel_id:

            log(
                "[ZOOM CHAT] "
                "No channel configured."
            )

            log(
                "[ZOOM CHAT] "
                "Finding/creating "
                f"'{DEFAULT_CHAT_CHANNEL}'..."
            )

            channel_result = (
                get_or_create_zoom_channel(
                    DEFAULT_CHAT_CHANNEL
                )
            )

            if not channel_result.get(
                "success"
            ):

                log(
                    "[ZOOM CHAT] "
                    "Could not find/create channel."
                )

                log(
                    f"[ZOOM CHAT] Details: "
                    f"{channel_result}"
                )

                return False

            channel_id = (
                channel_result.get(
                    "channel_id"
                )
            )

            if not channel_id:

                log(
                    "[ZOOM CHAT] "
                    "Channel ID was not returned."
                )

                return False

            # Store for current process
            os.environ[
                "ZOOM_CHAT_CHANNEL"
            ] = channel_id

            log(
                "[ZOOM CHAT] Channel configured:"
            )

            log(
                f"[ZOOM CHAT] {channel_id}"
            )

        # ====================================================
        # SEND MESSAGE
        # ====================================================

        log(
            "[ZOOM CHAT] "
            "Sending meeting summary..."
        )

        chat_result = (
            send_meeting_summary_to_zoom(
                meeting_title=meeting_title,

                summary=summary,

                key_points=key_points,

                decisions=decisions,

                open_questions=open_questions,

                action_items=action_items,

                filename=file_path.name,

                channel_id=channel_id,
            )
        )

        # ====================================================
        # RESULT
        # ====================================================

        if chat_result.get(
            "success"
        ):

            log(
                "✅ [ZOOM CHAT] "
                "Meeting summary sent successfully."
            )

            return True

        log(
            "❌ [ZOOM CHAT] "
            "Failed to send meeting summary."
        )

        log(
            f"[ZOOM CHAT] Details: {chat_result}"
        )

        return False

    except Exception as e:

        log(
            f"❌ [ZOOM CHAT] "
            f"Unexpected error: {e}"
        )

        return False


# ============================================================
# PROCESS RECORDING
# ============================================================

def process_recording(
    file_path: Path,
):

    file_key = str(
        file_path.resolve()
    )

    # ========================================================
    # DUPLICATE CHECK
    # ========================================================

    if is_already_processed(
        file_path
    ):

        log(
            f"Skipping already processed recording: "
            f"{file_path.name}"
        )

        return

    # ========================================================
    # PREVENT DUPLICATE THREADS
    # ========================================================

    with processing_lock:

        if file_key in processing_files:

            return

        processing_files.add(
            file_key
        )

    try:

        # ====================================================
        # RECORDING INFORMATION
        # ====================================================

        log("=" * 60)

        log(
            "NEW ZOOM RECORDING DETECTED"
        )

        log(
            f"File: {file_path}"
        )

        try:

            file_size = (
                file_path.stat().st_size
                / (1024 * 1024)
            )

        except OSError:

            file_size = 0

        log(
            f"Size: {file_size:.2f} MB"
        )

        log("=" * 60)

        # ====================================================
        # WAIT UNTIL COMPLETE
        # ====================================================

        if not wait_until_file_is_stable(
            file_path
        ):

            log(
                "Recording did not become stable."
            )

            return

        # ====================================================
        # WHISPER
        # ====================================================

        log(
            "Starting Whisper transcription..."
        )

        try:

            transcript = transcribe_audio(
                str(file_path)
            )

        except Exception as e:

            log(
                f"Transcription failed: {e}"
            )

            return

        if not transcript:

            log(
                "Transcription returned empty text."
            )

            return

        log(
            "Whisper transcription completed."
        )

        # ====================================================
        # SAVE TRANSCRIPT
        # ====================================================

        transcript_path = (
            file_path.with_suffix(
                ".transcript.txt"
            )
        )

        try:

            with open(
                transcript_path,
                "w",
                encoding="utf-8",
            ) as f:

                f.write(
                    transcript
                )

            log(
                f"Transcript saved: "
                f"{transcript_path}"
            )

        except Exception as e:

            log(
                f"Failed to save transcript: {e}"
            )

            return

        # ====================================================
        # OLLAMA
        # ====================================================

        log(
            "Starting Ollama meeting analysis..."
        )

        try:

            summary_data = summarize_text(
                transcript
            )

        except Exception as e:

            log(
                f"Summarization failed: {e}"
            )

            return

        if not isinstance(
            summary_data,
            dict,
        ):

            log(
                "Summarizer returned invalid data."
            )

            return

        log(
            "Meeting analysis completed."
        )

        # ====================================================
        # SAVE SUMMARY JSON
        # ====================================================

        summary_path = (
            file_path.with_suffix(
                ".summary.json"
            )
        )

        try:

            with open(
                summary_path,
                "w",
                encoding="utf-8",
            ) as f:

                json.dump(
                    summary_data,
                    f,
                    indent=4,
                    ensure_ascii=False,
                )

            log(
                f"Summary saved: "
                f"{summary_path}"
            )

        except Exception as e:

            log(
                f"Failed to save summary: {e}"
            )

            return

        # ====================================================
        # MONGODB
        # ====================================================

        log(
            "Saving meeting to MongoDB..."
        )

        mongodb_saved = (
            save_meeting_to_mongodb(
                file_path=file_path,

                transcript=transcript,

                summary_data=summary_data,
            )
        )

        if not mongodb_saved:

            log(
                "MongoDB save failed."
            )

            # IMPORTANT:
            # Do not mark as processed.
            return

        # ====================================================
        # ZOOM TEAM CHAT
        # ====================================================

        zoom_chat_sent = (
            send_summary_to_zoom_chat(
                file_path=file_path,

                summary_data=summary_data,
            )
        )

        # ====================================================
        # FINAL RESULT
        # ====================================================

        meeting_title = (
            summary_data.get(
                "meeting_title",
                "Meeting",
            )
        )

        action_items = (
            summary_data.get(
                "action_items",
                [],
            )
        )

        log("=" * 60)

        log(
            "ZOOM MEETING PROCESSING COMPLETE"
        )

        log(
            f"Meeting title: "
            f"{meeting_title}"
        )

        log(
            f"Action items: "
            f"{len(action_items)}"
        )

        log(
            "Whisper: DONE"
        )

        log(
            "Ollama: DONE"
        )

        log(
            "MongoDB: SAVED"
        )

        log(
            "Local transcript: SAVED"
        )

        log(
            "Local summary JSON: SAVED"
        )

        log(
    f"Zoom Team Chat: "
    f"{'SENT' if zoom_chat_sent else 'FAILED'}"
)

        log(
            f"Zoom Team Chat: "
            f"{'SENT' if zoom_chat_sent else 'FAILED'}"
        )

        log("=" * 60)

        # ====================================================
        # MARK PROCESSED
        # ====================================================

        if mark_as_processed(
            file_path
        ):

            log(
                "Recording permanently marked as processed."
            )

        else:

            log(
                "WARNING: Processed marker could not "
                "be created."
            )

    except Exception as e:

        log(
            f"Unexpected processing error: {e}"
        )

    finally:

        with processing_lock:

            processing_files.discard(
                file_key
            )


# ============================================================
# SCAN RECORDINGS
# ============================================================

def scan_recordings():

    if not ZOOM_RECORDING_DIR.exists():

        log(
            f"Zoom recording directory does not exist: "
            f"{ZOOM_RECORDING_DIR}"
        )

        return

    audio_files = find_audio_files()

    if not audio_files:

        return

    for file_path in audio_files:

        if is_already_processed(
            file_path
        ):

            continue

        file_key = str(
            file_path.resolve()
        )

        with processing_lock:

            if file_key in processing_files:

                continue

        thread = threading.Thread(
            target=process_recording,

            args=(file_path,),

            name=(
                f"ZoomProcessor-"
                f"{file_path.stem}"
            ),

            daemon=True,
        )

        thread.start()


# ============================================================
# WATCHER LOOP
# ============================================================

def watcher_loop():

    global watcher_running

    log(
        "Zoom recording watcher started."
    )

    log(
        f"Watching directory: "
        f"{ZOOM_RECORDING_DIR}"
    )

    log(
        f"Check interval: "
        f"{CHECK_INTERVAL} seconds"
    )

    watcher_running = True

    while watcher_running:

        try:

            scan_recordings()

        except Exception as e:

            log(
                f"Watcher loop error: {e}"
            )

        time.sleep(
            CHECK_INTERVAL
        )

    log(
        "Zoom recording watcher stopped."
    )


# ============================================================
# START WATCHER
# ============================================================

def start_zoom_recording_watcher():

    global watcher_thread
    global watcher_running

    if watcher_thread is not None:

        if watcher_thread.is_alive():

            log(
                "Zoom recording watcher "
                "is already running."
            )

            return

    watcher_running = True

    watcher_thread = threading.Thread(
        target=watcher_loop,

        name="ZoomRecordingWatcher",

        daemon=True,
    )

    watcher_thread.start()

    log(
        "Zoom recording watcher thread started."
    )


# ============================================================
# STOP WATCHER
# ============================================================

def stop_zoom_recording_watcher():

    global watcher_running

    watcher_running = False

    log(
        "Stopping Zoom recording watcher..."
    )


# ============================================================
# STATUS
# ============================================================

def get_watcher_status():

    return {

        "running":
            watcher_running,

        "watching_directory":
            str(
                ZOOM_RECORDING_DIR
            ),

        "directory_exists":
            ZOOM_RECORDING_DIR.exists(),

        "processed_files":
            len(
                processed_files
            ),

        "processing_files":
            len(
                processing_files
            ),

        "zoom_chat_configured":
            bool(
                get_env(
                    "ZOOM_CHAT_CHANNEL"
                )
            ),
    }