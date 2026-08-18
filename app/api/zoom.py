# ============================================================
# app/routes/zoom.py
# ============================================================

import os
import json
import hashlib
import hmac
import secrets
import urllib.parse
import threading

from pathlib import Path

import requests

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.transcription import transcribe_audio
from app.services.summarizer import summarize_text
from app.database import meetings_collection

from app.services.zoom_auth import (
    get_zoom_access_token,
    refresh_zoom_access_token,
    zoom_api_request,
)

from app.services.zoom_chat import (
    send_zoom_chat_message,
    create_zoom_channel,
    list_zoom_channels,
    find_zoom_channel,
    get_or_create_zoom_channel,
    send_meeting_summary_to_zoom,
    send_test_zoom_message,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/zoom",
    tags=["Zoom"],
)


# ============================================================
# CONFIGURATION
# ============================================================

ZOOM_API_BASE = "https://api.zoom.us/v2"

ZOOM_OAUTH_URL = "https://zoom.us/oauth/token"

ZOOM_DOWNLOAD_DIR = Path(
    os.getenv(
        "ZOOM_CLOUD_RECORDING_DIR",
        r"C:\Users\BN Com\Documents\Zoom\CloudRecordings",
    )
)

ZOOM_DOWNLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# OAUTH STATE
# ============================================================

oauth_states = set()


# ============================================================
# RECORDING PROCESSING STATE
# ============================================================

processing_recordings = set()

processing_lock = threading.Lock()


# ============================================================
# ENVIRONMENT HELPER
# ============================================================

def get_env(
    name: str,
    default: str | None = None,
):
    value = os.getenv(name)

    if value is None:
        return default

    value = value.strip()

    if not value:
        return default

    return value


# ============================================================
# SAFE FILE NAME
# ============================================================

def safe_filename(
    filename: str,
):
    invalid_chars = (
        "\\",
        "/",
        ":",
        "*",
        "?",
        '"',
        "<",
        ">",
        "|",
    )

    for char in invalid_chars:
        filename = filename.replace(
            char,
            "_",
        )

    return filename


# ============================================================
# ZOOM USER
# ============================================================

@router.get("/me")
async def get_zoom_me():

    response, error = zoom_api_request(
        "GET",
        f"{ZOOM_API_BASE}/users/me",
    )

    if error:

        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": error,
            },
        )

    try:

        return response.json()

    except Exception:

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Invalid Zoom response.",
            },
        )
@router.get("/status")
def zoom_status():
    access_token = os.getenv("ZOOM_ACCESS_TOKEN")

    return {
        "watcher": "running",
        "zoom_chat": "connected" if access_token else "not_configured",
        "access_token_configured": bool(access_token),
    }

# ============================================================
# ZOOM USERS
# ============================================================

@router.get("/users")
async def get_zoom_users():

    response, error = zoom_api_request(
        "GET",
        f"{ZOOM_API_BASE}/users",
    )

    if error:

        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": error,
            },
        )

    try:

        return response.json()

    except Exception:

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Invalid Zoom response.",
            },
        )


# ============================================================
# ZOOM TEAM CHAT
# ============================================================

@router.get("/chat/channels")
async def get_zoom_chat_channels():

    result = list_zoom_channels()

    if not result.get("success"):

        return JSONResponse(
            status_code=result.get(
                "status_code",
                400,
            ),
            content=result,
        )

    return result


# ============================================================
# FIND CHANNEL
# ============================================================

@router.get("/chat/channels/find")
async def find_zoom_chat_channel(
    name: str,
):

    if not name or not name.strip():

        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Channel name is required.",
            },
        )

    result = find_zoom_channel(
        name.strip()
    )

    if not result.get("success"):

        return JSONResponse(
            status_code=result.get(
                "status_code",
                400,
            ),
            content=result,
        )

    return result


# ============================================================
# CREATE CHANNEL
# ============================================================

@router.post("/chat/channels/create")
async def create_zoom_chat_channel(
    name: str,
):

    if not name or not name.strip():

        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Channel name is required.",
            },
        )

    channel_name = name.strip()

    result = create_zoom_channel(
        channel_name=channel_name,
    )

    if not result.get("success"):

        return JSONResponse(
            status_code=result.get(
                "status_code",
                400,
            ),
            content=result,
        )

    channel_id = result.get(
        "channel_id"
    )

    if channel_id:

        os.environ[
            "ZOOM_CHAT_CHANNEL"
        ] = channel_id

        print(
            "[ZOOM CHAT] "
            "ZOOM_CHAT_CHANNEL set to:"
        )

        print(channel_id)

    return result


# ============================================================
# GET OR CREATE CHANNEL
# ============================================================

@router.post("/chat/channels/get-or-create")
async def get_or_create_chat_channel(
    name: str,
):

    if not name or not name.strip():

        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Channel name is required.",
            },
        )

    channel_name = name.strip()

    result = get_or_create_zoom_channel(
        channel_name=channel_name,
    )

    if not result.get("success"):

        return JSONResponse(
            status_code=result.get(
                "status_code",
                400,
            ),
            content=result,
        )

    channel_id = result.get(
        "channel_id"
    )

    if channel_id:

        os.environ[
            "ZOOM_CHAT_CHANNEL"
        ] = channel_id

        print(
            "[ZOOM CHAT] "
            "ZOOM_CHAT_CHANNEL set to:"
        )

        print(channel_id)

    return result


# ============================================================
# TEST ZOOM TEAM CHAT
# ============================================================

@router.post("/chat/test")
async def test_zoom_chat():

    channel_id = get_env(
        "ZOOM_CHAT_CHANNEL"
    )

    if not channel_id:

        print(
            "[ZOOM CHAT] No channel configured."
        )

        print(
            "[ZOOM CHAT] Finding/creating "
            "AI Meeting Assistant channel..."
        )

        channel_result = (
            get_or_create_zoom_channel(
                "AI Meeting Assistant"
            )
        )

        if not channel_result.get(
            "success"
        ):

            return JSONResponse(
                status_code=channel_result.get(
                    "status_code",
                    400,
                ),
                content=channel_result,
            )

        channel_id = (
            channel_result.get(
                "channel_id"
            )
        )

        if not channel_id:

            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error":
                        "Zoom channel was found/created "
                        "but no channel ID was returned.",
                    "details":
                        channel_result,
                },
            )

        os.environ[
            "ZOOM_CHAT_CHANNEL"
        ] = channel_id

    result = send_test_zoom_message(
        channel_id=channel_id,
    )

    if not result.get(
        "success"
    ):

        return JSONResponse(
            status_code=result.get(
                "status_code",
                400,
            ),
            content=result,
        )

    return {
        "success": True,
        "message":
            "Zoom Team Chat test message sent successfully.",
        "channel_id":
            channel_id,
        "result":
            result,
    }


# ============================================================
# SEND CUSTOM CHAT MESSAGE
# ============================================================

@router.post("/chat/send")
async def send_chat_message(
    message: str,
    channel_id: str | None = None,
    contact_email: str | None = None,
):

    if not message or not message.strip():

        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Message is required.",
            },
        )

    if channel_id and contact_email:

        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error":
                    "Provide channel_id OR contact_email, "
                    "not both.",
            },
        )

    if not channel_id and not contact_email:

        channel_id = get_env(
            "ZOOM_CHAT_CHANNEL"
        )

    if not channel_id and not contact_email:

        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error":
                    "No destination configured. "
                    "Provide channel_id or contact_email.",
            },
        )

    result = send_zoom_chat_message(
        message=message,
        to_channel=channel_id,
        to_contact=contact_email,
    )

    if not result.get(
        "success"
    ):

        return JSONResponse(
            status_code=result.get(
                "status_code",
                400,
            ),
            content=result,
        )

    return result


# ============================================================
# DOWNLOAD ZOOM RECORDING
# ============================================================

def download_zoom_recording(
    download_url: str,
    destination: Path,
):

    access_token = get_zoom_access_token()

    if not access_token:

        return {
            "success": False,
            "status_code": 401,
            "error":
                "ZOOM_ACCESS_TOKEN is not configured.",
        }

    headers = {
        "Authorization":
            f"Bearer {access_token}",
    }

    try:

        response = requests.get(
            download_url,
            headers=headers,
            stream=True,
            allow_redirects=True,
            timeout=120,
        )

    except requests.RequestException as e:

        return {
            "success": False,
            "error":
                "Recording download failed.",
            "details":
                str(e),
        }

    if response.status_code == 401:

        print(
            "[ZOOM] Recording download token expired."
        )

        refresh_result = (
            refresh_zoom_access_token()
        )

        if not refresh_result.get(
            "success"
        ):

            return {
                "success": False,
                "status_code": 401,
                "error":
                    "Recording download unauthorized "
                    "and token refresh failed.",
                "details":
                    refresh_result,
            }

        new_access_token = (
            refresh_result.get(
                "access_token"
            )
        )

        if not new_access_token:

            return {
                "success": False,
                "status_code": 401,
                "error":
                    "Token refresh returned no access token.",
            }

        try:

            response = requests.get(
                download_url,
                headers={
                    "Authorization":
                        f"Bearer {new_access_token}"
                },
                stream=True,
                allow_redirects=True,
                timeout=120,
            )

        except requests.RequestException as e:

            return {
                "success": False,
                "error":
                    "Recording download failed "
                    "after token refresh.",
                "details":
                    str(e),
            }

    if response.status_code != 200:

        return {
            "success": False,
            "status_code":
                response.status_code,
            "error":
                "Zoom recording download failed.",
            "details":
                response.text[:1000],
        }

    try:

        with open(
            destination,
            "wb",
        ) as file:

            for chunk in response.iter_content(
                chunk_size=1024 * 1024
            ):

                if chunk:
                    file.write(chunk)

    except Exception as e:

        return {
            "success": False,
            "error":
                "Failed to save recording.",
            "details":
                str(e),
        }

    return {
        "success": True,
        "path":
            str(destination),
    }


# ============================================================
# PROCESS ZOOM CLOUD RECORDING
# ============================================================

def process_zoom_recording(
    recording_file: dict,
    meeting_info: dict,
    event_type: str,
):

    recording_id = recording_file.get("id")

    download_url = recording_file.get(
        "download_url"
    )

    recording_type = recording_file.get(
        "recording_type"
    )

    file_extension = recording_file.get(
        "file_extension",
        "M4A",
    )

    file_name = recording_file.get(
        "file_name",
        f"zoom_recording_{recording_id}."
        f"{file_extension.lower()}",
    )

    allowed_audio_types = {
        "audio_only",
        "audio_only_each_participant",
    }

    if recording_type not in allowed_audio_types:

        print(
            "[ZOOM] Ignoring recording type:",
            recording_type,
        )

        return

    if not recording_id:

        print(
            "[ZOOM] Recording ID missing."
        )

        return

    if not download_url:

        print(
            "[ZOOM] Recording download URL missing."
        )

        return

    with processing_lock:

        if recording_id in processing_recordings:

            print(
                "[ZOOM] Recording already processing:",
                recording_id,
            )

            return

        processing_recordings.add(
            recording_id
        )

    try:

        print(
            "\n========================================"
        )

        print(
            "ZOOM CLOUD RECORDING PROCESSING"
        )

        print(
            "========================================"
        )

        print(
            f"Recording ID: {recording_id}"
        )

        print(
            f"Recording type: {recording_type}"
        )

        print(
            "Meeting topic:",
            meeting_info.get("topic"),
        )

        # ====================================================
        # FILE PATH
        # ====================================================

        safe_name = safe_filename(
            file_name
        )

        audio_path = (
            ZOOM_DOWNLOAD_DIR
            / f"{recording_id}_{safe_name}"
        )

        # ====================================================
        # DOWNLOAD
        # ====================================================

        print(
            "[ZOOM] Downloading recording..."
        )

        download_result = (
            download_zoom_recording(
                download_url,
                audio_path,
            )
        )

        if not download_result.get(
            "success"
        ):

            print(
                "[ZOOM] Download failed:",
                download_result,
            )

            return

        print(
            "[ZOOM] Recording downloaded:",
            audio_path,
        )

        # ====================================================
        # WHISPER
        # ====================================================

        print(
            "[ZOOM] Starting Whisper transcription..."
        )

        try:

            transcript = transcribe_audio(
                str(audio_path)
            )

        except Exception as e:

            print(
                "[ZOOM] Transcription failed:",
                e,
            )

            return

        if not transcript:

            print(
                "[ZOOM] Empty transcript."
            )

            return

        print(
            "[ZOOM] Whisper transcription completed."
        )

        # ====================================================
        # TRANSCRIPT
        # ====================================================

        transcript_path = (
            audio_path.with_suffix(
                ".transcript.txt"
            )
        )

        with open(
            transcript_path,
            "w",
            encoding="utf-8",
        ) as file:

            file.write(
                transcript
            )

        # ====================================================
        # OLLAMA
        # ====================================================

        print(
            "[ZOOM] Starting Ollama analysis..."
        )

        try:

            summary_data = summarize_text(
                transcript
            )

        except Exception as e:

            print(
                "[ZOOM] Summarization failed:",
                e,
            )

            return

        if not isinstance(
            summary_data,
            dict,
        ):

            print(
                "[ZOOM] Invalid summary returned."
            )

            return

        print(
            "[ZOOM] Meeting analysis completed."
        )

        # ====================================================
        # SUMMARY FILE
        # ====================================================

        summary_path = (
            audio_path.with_suffix(
                ".summary.json"
            )
        )

        with open(
            summary_path,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                summary_data,
                file,
                indent=4,
                ensure_ascii=False,
            )

        # ====================================================
        # SUMMARY DATA
        # ====================================================

        meeting_title = (
            summary_data.get(
                "meeting_title"
            )
            or
            meeting_info.get(
                "topic",
                "Zoom Meeting",
            )
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

        # ====================================================
        # MONGODB
        # ====================================================

        print(
            "[ZOOM] Saving meeting to MongoDB..."
        )

        meeting_document = {

            "source":
                "zoom_cloud",

            "event_type":
                event_type,

            "zoom": {

                "meeting_id":
                    meeting_info.get("id"),

                "meeting_uuid":
                    meeting_info.get("uuid"),

                "host_id":
                    meeting_info.get("host_id"),

                "host_email":
                    meeting_info.get("host_email"),

                "topic":
                    meeting_info.get("topic"),

                "start_time":
                    meeting_info.get("start_time"),

                "duration":
                    meeting_info.get("duration"),

                "recording_id":
                    recording_id,

                "recording_type":
                    recording_type,

                "recording_start":
                    recording_file.get(
                        "recording_start"
                    ),

                "recording_end":
                    recording_file.get(
                        "recording_end"
                    ),

                "file_name":
                    file_name,
            },

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

            "audio_file":
                str(audio_path),

            "transcript_file":
                str(transcript_path),

            "summary_file":
                str(summary_path),

        }

        result = meetings_collection.insert_one(
            meeting_document
        )

        print(
            "[ZOOM] Meeting saved to MongoDB."
        )

        print(
            "[ZOOM] MongoDB ID:",
            result.inserted_id,
        )

        # ====================================================
        # ZOOM TEAM CHAT
        # ====================================================

        channel_id = get_env(
            "ZOOM_CHAT_CHANNEL"
        )

        if not channel_id:

            print(
                "[ZOOM CHAT] No channel configured."
            )

            print(
                "[ZOOM CHAT] Finding/creating "
                "AI Meeting Assistant..."
            )

            channel_result = (
                get_or_create_zoom_channel(
                    "AI Meeting Assistant"
                )
            )

            if channel_result.get(
                "success"
            ):

                channel_id = (
                    channel_result.get(
                        "channel_id"
                    )
                )

                if channel_id:

                    os.environ[
                        "ZOOM_CHAT_CHANNEL"
                    ] = channel_id

            else:

                print(
                    "[ZOOM CHAT] Could not "
                    "create/find channel:"
                )

                print(
                    channel_result
                )

        if channel_id:

            print(
                "[ZOOM CHAT] Sending meeting summary..."
            )

            chat_result = (
                send_meeting_summary_to_zoom(
                    meeting_title=meeting_title,

                    summary=summary,

                    key_points=key_points,

                    decisions=decisions,

                    open_questions=open_questions,

                    action_items=action_items,

                    filename=file_name,

                    channel_id=channel_id,
                )
            )

            if chat_result.get(
                "success"
            ):

                print(
                    "✅ [ZOOM CHAT] "
                    "Meeting summary sent."
                )

            else:

                print(
                    "❌ [ZOOM CHAT] "
                    "Failed to send meeting summary:"
                )

                print(
                    chat_result
                )

        else:

            print(
                "[ZOOM CHAT] "
                "No Zoom Team Chat channel available."
            )

        # ====================================================
        # COMPLETE
        # ====================================================

        print(
            "\n========================================"
        )

        print(
            "ZOOM CLOUD PROCESSING COMPLETE"
        )

        print(
            "========================================"
        )

        print(
            f"Meeting: {meeting_title}"
        )

        print(
            f"Action items: {len(action_items)}"
        )

        print(
            f"MongoDB ID: {result.inserted_id}"
        )

        print(
            "Zoom Chat:",
            "SENT" if channel_id else "NOT SENT",
        )

        print(
            "========================================\n"
        )

    except Exception as e:

        print(
            "[ZOOM] Unexpected processing error:",
            e,
        )

    finally:

        with processing_lock:

            processing_recordings.discard(
                recording_id
            )


# ============================================================
# START BACKGROUND PROCESSING
# ============================================================

def start_recording_processing(
    recording_file: dict,
    meeting_info: dict,
    event_type: str,
):

    recording_id = recording_file.get(
        "id",
        "unknown",
    )

    thread = threading.Thread(
        target=process_zoom_recording,

        args=(
            recording_file,
            meeting_info,
            event_type,
        ),

        name=f"ZoomRecording-{recording_id}",

        daemon=True,
    )

    thread.start()


# ============================================================
# ZOOM WEBHOOK
# ============================================================

@router.post("/webhook")
async def zoom_webhook(
    request: Request,
):

    try:

        body = await request.json()

    except Exception:

        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error":
                    "Invalid JSON received.",
            },
        )

    print(
        "\n========================================"
    )

    print(
        "ZOOM WEBHOOK RECEIVED"
    )

    print(
        "========================================"
    )

    event_type = body.get(
        "event"
    )

    print(
        "Event:",
        event_type,
    )

    # ========================================================
    # URL VALIDATION
    # ========================================================

    if event_type == "endpoint.url_validation":

        payload = body.get(
            "payload",
            {},
        )

        plain_token = payload.get(
            "plainToken"
        )

        if not plain_token:

            return JSONResponse(
                status_code=400,
                content={
                    "error":
                        "plainToken missing.",
                },
            )

        secret_token = get_env(
            "ZOOM_WEBHOOK_SECRET_TOKEN"
        )

        if not secret_token:

            return JSONResponse(
                status_code=500,
                content={
                    "error":
                        "ZOOM_WEBHOOK_SECRET_TOKEN "
                        "is not configured.",
                },
            )

        encrypted_token = hmac.new(
            secret_token.encode("utf-8"),
            plain_token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return {
            "plainToken":
                plain_token,

            "encryptedToken":
                encrypted_token,
        }

    # ========================================================
    # NORMAL PAYLOAD
    # ========================================================

    payload = body.get(
        "payload",
        {},
    )

    meeting_info = payload.get(
        "object",
        {},
    )

    print(
        "Meeting ID:",
        meeting_info.get("id"),
    )

    print(
        "Meeting UUID:",
        meeting_info.get("uuid"),
    )

    # ========================================================
    # MEETING STARTED
    # ========================================================

    if event_type == "meeting.started":

        print(
            "[ZOOM] Meeting started."
        )

        return {
            "status":
                "received",

            "event":
                event_type,

            "message":
                "Meeting started event received.",
        }

    # ========================================================
    # MEETING ENDED
    # ========================================================

    if event_type == "meeting.ended":

        print(
            "[ZOOM] Meeting ended."
        )

        return {
            "status":
                "received",

            "event":
                event_type,

            "message":
                "Meeting ended event received.",
        }

    # ========================================================
    # RECORDING COMPLETED
    # ========================================================

    if event_type in {
        "recording.completed",
        "recording.transcript_completed",
    }:

        recording_files = (
            meeting_info.get(
                "recording_files",
                [],
            )
        )

        print(
            "[ZOOM] Recording files received:",
            len(recording_files),
        )

        started = 0

        for recording_file in recording_files:

            if recording_file.get(
                "status"
            ) != "completed":

                continue

            if not recording_file.get(
                "download_url"
            ):

                continue

            recording_type = (
                recording_file.get(
                    "recording_type"
                )
            )

            if recording_type not in {
                "audio_only",
                "audio_only_each_participant",
            }:

                continue

            start_recording_processing(
                recording_file,
                meeting_info,
                event_type,
            )

            started += 1

        print(
            "[ZOOM] Background jobs started:",
            started,
        )

        return {
            "status":
                "received",

            "event":
                event_type,

            "recording_files":
                len(recording_files),

            "processing_started":
                started,
        }

    # ========================================================
    # OTHER EVENTS
    # ========================================================

    print(
        "[ZOOM] Event received but no processing "
        "handler is configured."
    )

    return {
        "status":
            "received",

        "event":
            event_type,
    }


# ============================================================
# ZOOM OAUTH LOGIN
# ============================================================

@router.get("/oauth/login")
async def zoom_oauth_login():

    client_id = get_env(
        "ZOOM_CLIENT_ID"
    )

    redirect_uri = get_env(
        "ZOOM_REDIRECT_URI",
        "http://localhost:8000/zoom/oauth/callback",
    )

    if not client_id:

        return JSONResponse(
            status_code=500,
            content={
                "error":
                    "ZOOM_CLIENT_ID is not configured.",
            },
        )

    state = secrets.token_urlsafe(
        32
    )

    oauth_states.add(
        state
    )

    params = {

        "response_type":
            "code",

        "client_id":
            client_id,

        "redirect_uri":
            redirect_uri,

        "state":
            state,
    }

    authorization_url = (
        "https://zoom.us/oauth/authorize?"
        +
        urllib.parse.urlencode(
            params
        )
    )

    return {

        "authorization_url":
            authorization_url,

        "message":
            "Open authorization_url in your browser.",
    }


# ============================================================
# OAUTH CALLBACK
# ============================================================

@router.get("/oauth/callback")
async def zoom_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):

    if error:

        return JSONResponse(
            status_code=400,
            content={
                "error":
                    "Zoom authorization failed.",

                "zoom_error":
                    error,

                "description":
                    error_description,
            },
        )

    if not code:

        return JSONResponse(
            status_code=400,
            content={
                "error":
                    "Authorization code was not provided.",
            },
        )

    if not state:

        return JSONResponse(
            status_code=400,
            content={
                "error":
                    "OAuth state was not provided.",
            },
        )

    if state not in oauth_states:

        return JSONResponse(
            status_code=400,
            content={
                "error":
                    "Invalid or expired OAuth state.",
            },
        )

    oauth_states.discard(
        state
    )

    client_id = get_env(
        "ZOOM_CLIENT_ID"
    )

    client_secret = get_env(
        "ZOOM_CLIENT_SECRET"
    )

    redirect_uri = get_env(
        "ZOOM_REDIRECT_URI",
        "http://localhost:8000/zoom/oauth/callback",
    )

    if not client_id:

        return JSONResponse(
            status_code=500,
            content={
                "error":
                    "ZOOM_CLIENT_ID is not configured.",
            },
        )

    if not client_secret:

        return JSONResponse(
            status_code=500,
            content={
                "error":
                    "ZOOM_CLIENT_SECRET is not configured.",
            },
        )

    try:

        response = requests.post(
            ZOOM_OAUTH_URL,

            data={
                "grant_type":
                    "authorization_code",

                "code":
                    code,

                "redirect_uri":
                    redirect_uri,
            },

            auth=(
                client_id,
                client_secret,
            ),

            timeout=30,
        )

    except requests.RequestException as e:

        return JSONResponse(
            status_code=500,
            content={
                "error":
                    "Unable to connect to Zoom.",

                "details":
                    str(e),
            },
        )

    if response.status_code != 200:

        return JSONResponse(
            status_code=response.status_code,
            content={
                "error":
                    "Zoom token exchange failed.",

                "details":
                    response.text,
            },
        )

    try:

        token_data = response.json()

    except Exception:

        return JSONResponse(
            status_code=500,
            content={
                "error":
                    "Zoom returned invalid token response.",
            },
        )

    access_token = token_data.get(
        "access_token"
    )

    refresh_token = token_data.get(
        "refresh_token"
    )

    if not access_token:

        return JSONResponse(
            status_code=500,
            content={
                "error":
                    "Zoom did not return access token.",
            },
        )

    os.environ[
        "ZOOM_ACCESS_TOKEN"
    ] = access_token

    if refresh_token:

        os.environ[
            "ZOOM_REFRESH_TOKEN"
        ] = refresh_token

    print(
        "[ZOOM] OAuth authorization successful."
    )

    print(
        "[ZOOM] Access token stored."
    )

    print(
        "[ZOOM] Refresh token stored:",
        bool(refresh_token),
    )

    return {

        "message":
            "Zoom authorization successful.",

        "token_type":
            token_data.get("token_type"),

        "expires_in":
            token_data.get("expires_in"),

        "scope":
            token_data.get("scope"),

        "access_token_received":
            True,

        "refresh_token_received":
            bool(refresh_token),
    }


# ============================================================
# TOKEN STATUS
# ============================================================

@router.get("/token-status")
async def token_status():

    access_token = get_env(
        "ZOOM_ACCESS_TOKEN"
    )

    refresh_token = get_env(
        "ZOOM_REFRESH_TOKEN"
    )

    channel_id = get_env(
        "ZOOM_CHAT_CHANNEL"
    )

    return {

        "access_token_configured":
            bool(access_token),

        "access_token_length":
            len(access_token)
            if access_token
            else 0,

        "refresh_token_configured":
            bool(refresh_token),

        "refresh_token_length":
            len(refresh_token)
            if refresh_token
            else 0,

        "chat_channel_configured":
            bool(channel_id),

        "chat_channel_id":
            channel_id,
    }


# ============================================================
# MANUAL TOKEN REFRESH
# ============================================================

@router.post("/refresh-token")
async def refresh_token():

    result = refresh_zoom_access_token()

    if not result.get(
        "success"
    ):

        return JSONResponse(
            status_code=400,
            content=result,
        )

    return {

        "message":
            "Zoom access token refreshed successfully.",

        "expires_in":
            result.get("expires_in"),

        "scope":
            result.get("scope"),

        "access_token_received":
            True,

        "refresh_token_received":
            bool(
                result.get("refresh_token")
            ),
    }


# ============================================================
# TEST RECORDINGS API
# ============================================================

@router.get("/recordings/test")
async def test_zoom_recordings():

    url = (
        f"{ZOOM_API_BASE}"
        "/users/me/recordings"
    )

    response, error = zoom_api_request(
        "GET",
        url,
    )

    if error:

        return JSONResponse(
            status_code=401,
            content=error,
        )

    if response.status_code != 200:

        return JSONResponse(
            status_code=response.status_code,
            content={
                "error":
                    "Zoom recordings API failed.",

                "details":
                    response.text,
            },
        )

    try:

        data = response.json()

    except Exception:

        return JSONResponse(
            status_code=500,
            content={
                "error":
                    "Invalid Zoom response.",
            },
        )

    recordings = data.get(
        "meetings",
        [],
    )

    return {

        "message":
            "Zoom recordings API is working.",

        "total_records":
            len(recordings),

        "page_count":
            data.get("page_count"),

        "page_size":
            data.get("page_size"),

        "next_page_token":
            bool(
                data.get("next_page_token")
            ),

        "recordings":
            recordings,
    }


# ============================================================
# GET RECORDINGS
# ============================================================

@router.get("/recordings")
async def get_zoom_recordings():

    url = (
        f"{ZOOM_API_BASE}"
        "/users/me/recordings"
    )

    response, error = zoom_api_request(
        "GET",
        url,
    )

    if error:

        return JSONResponse(
            status_code=401,
            content=error,
        )

    if response.status_code != 200:

        return JSONResponse(
            status_code=response.status_code,
            content={
                "error":
                    "Zoom recordings API failed.",

                "details":
                    response.text,
            },
        )

    try:

        return response.json()

    except Exception:

        return JSONResponse(
            status_code=500,
            content={
                "error":
                    "Zoom returned invalid recordings data.",
            },
        )


# ============================================================
# HEALTH CHECK
# ============================================================

@router.get("/health")
async def zoom_health():

    return {

        "zoom_router":
            "running",

        "oauth_client_configured":
            bool(
                get_env(
                    "ZOOM_CLIENT_ID"
                )
            ),

        "access_token_configured":
            bool(
                get_env(
                    "ZOOM_ACCESS_TOKEN"
                )
            ),

        "refresh_token_configured":
            bool(
                get_env(
                    "ZOOM_REFRESH_TOKEN"
                )
            ),

        "zoom_chat_channel_configured":
            bool(
                get_env(
                    "ZOOM_CHAT_CHANNEL"
                )
            ),

        "webhook":
            "/zoom/webhook",

        "oauth_login":
            "/zoom/oauth/login",

        "oauth_callback":
            "/zoom/oauth/callback",

        "recordings":
            "/zoom/recordings",

        "chat_channels":
            "/zoom/chat/channels",

        "chat_find":
            "/zoom/chat/channels/find",

        "chat_create_channel":
            "/zoom/chat/channels/create",

        "chat_get_or_create":
            "/zoom/chat/channels/get-or-create",

        "chat_test":
            "/zoom/chat/test",

        "chat_send":
            "/zoom/chat/send",
    }