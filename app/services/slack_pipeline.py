import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.database import slack_meetings_collection
from app.services.transcription import transcribe_audio
from app.services.summarizer import summarize_text
from app.services.embedding import create_meeting_embedding
from app.services.jira import create_jira_issue


logger = logging.getLogger("slack_pipeline")


# ============================================================
# PROJECT ROOT
# ============================================================
#
# audio_file is stored as a path relative to the project root
# (e.g. "recordings/slack_huddle_<id>.wav" or the Windows-style
# "recordings\\slack_huddle_<id>.wav"). The pipeline can run in
# a background thread from a process whose CWD is not the
# project root, so resolve against this file's own location
# rather than os.getcwd().

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve_audio_path(audio_file: str) -> Path:
    normalized = str(audio_file).replace("\\", "/")

    path = Path(normalized)

    if not path.is_absolute():
        path = PROJECT_ROOT / path

    return path.resolve()


# ============================================================
# FAILURE HELPER
# ============================================================

def _mark_failed(huddle_id, stage, error):

    logger.error(
        "[SLACK PIPELINE] Processing failed | "
        "huddle=%s | stage=%s | error=%s",
        huddle_id,
        stage,
        error
    )

    slack_meetings_collection.update_one(
        {
            "huddle_id": huddle_id
        },
        {
            "$set": {
                "processing_status": "failed",
                "processing_error": f"{stage}: {error}",
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )


# ============================================================
# PIPELINE
# ============================================================

def _run_pipeline(meeting):
    """
    Runs transcription -> summarization -> action items ->
    embedding for one claimed slack_meetings document, saving
    results back into that same document as each stage
    completes. Runs in a background thread (see
    trigger_slack_meeting_processing) so it never blocks the
    Slack Socket Mode event loop.
    """

    huddle_id = meeting["huddle_id"]

    stage = "lookup"

    logger.info(
        "[SLACK PIPELINE] Processing started | huddle=%s",
        huddle_id
    )

    try:

        # ====================================================
        # RESOLVE AUDIO PATH
        # ====================================================

        stage = "transcription"

        audio_path = _resolve_audio_path(
            meeting.get("audio_file")
        )

        if not audio_path.exists():

            raise FileNotFoundError(
                f"Audio file not found: {audio_path}"
            )

        # ====================================================
        # TRANSCRIPTION
        # ====================================================

        logger.info(
            "[SLACK PIPELINE] Transcription started | huddle=%s",
            huddle_id
        )

        transcript = transcribe_audio(
            str(audio_path)
        )

        logger.info(
            "[SLACK PIPELINE] Transcription completed | huddle=%s",
            huddle_id
        )

        slack_meetings_collection.update_one(
            {
                "huddle_id": huddle_id
            },
            {
                "$set": {
                    "transcript": transcript,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )

        # ====================================================
        # SUMMARIZATION (also yields action_items)
        # ====================================================

        stage = "summarization"

        logger.info(
            "[SLACK PIPELINE] Summarization started | huddle=%s",
            huddle_id
        )

        summary_data = summarize_text(transcript)

        meeting_title = summary_data.get("meeting_title", "")
        summary = summary_data.get("summary", "")
        topics = summary_data.get("topics", [])
        decisions = summary_data.get("decisions", [])
        open_questions = summary_data.get("open_questions", [])
        key_points = summary_data.get("key_points", [])
        action_items = summary_data.get("action_items", [])

        logger.info(
            "[SLACK PIPELINE] Summarization completed | huddle=%s",
            huddle_id
        )

        slack_meetings_collection.update_one(
            {
                "huddle_id": huddle_id
            },
            {
                "$set": {
                    "meeting_title": meeting_title,
                    "summary": summary,
                    "topics": topics,
                    "decisions": decisions,
                    "open_questions": open_questions,
                    "key_points": key_points,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )

        # ====================================================
        # ACTION ITEMS
        # ====================================================
        #
        # summarize_text() already extracts action items under
        # the same "never invent owner/date/task" rules as the
        # rest of the summary, in one LLM call - this is the
        # existing reusable action-item logic (identical to
        # what app/api/upload.py already saves into
        # meetings_collection). Reusing it here avoids a
        # second, redundant LLM call and a second, incompatible
        # (plain-string) schema from app/services/action_items.py,
        # which nothing in the working pipeline currently uses.

        stage = "action_items"

        slack_meetings_collection.update_one(
            {
                "huddle_id": huddle_id
            },
            {
                "$set": {
                    "action_items": action_items,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )

        logger.info(
            "[SLACK PIPELINE] Action items completed | huddle=%s",
            huddle_id
        )

        # ====================================================
        # JIRA
        # ====================================================
        #
        # Best-effort: a Jira failure (bad credentials, network,
        # etc.) must not fail the overall pipeline, matching how
        # app/api/upload.py already isolates Jira errors.

        stage = "jira"

        try:

            for item in action_items:

                if not isinstance(item, dict):
                    continue

                task = item.get("task", "")

                if not task.strip():
                    continue

                jira_text = (
                    f"Task:\n{task}\n\n"
                    f"Owner:\n{item.get('owner', 'Not specified')}\n\n"
                    f"Due Date:\n{item.get('due_date', 'Not specified')}"
                )

                issue = create_jira_issue(jira_text)

                if issue and issue.get("key"):

                    logger.info(
                        "[SLACK PIPELINE] Jira issue created | "
                        "huddle=%s | key=%s",
                        huddle_id,
                        issue["key"]
                    )

                else:

                    logger.warning(
                        "[SLACK PIPELINE] Jira issue not created | "
                        "huddle=%s | task=%s",
                        huddle_id,
                        task
                    )

        except Exception as e:

            logger.error(
                "[SLACK PIPELINE] Jira step failed | huddle=%s | error=%s",
                huddle_id,
                e
            )

        # ====================================================
        # EMBEDDING
        # ====================================================

        stage = "embedding"

        embedding = create_meeting_embedding(
            meeting_title=meeting_title,
            summary=summary,
            topics=topics,
            decisions=decisions,
            open_questions=open_questions,
            key_points=key_points,
            action_items=action_items
        )

        if len(embedding) != 384:

            raise ValueError(
                f"Invalid embedding length: {len(embedding)}"
            )

        logger.info(
            "[SLACK PIPELINE] Embedding completed | huddle=%s",
            huddle_id
        )

        # ====================================================
        # COMPLETE
        # ====================================================

        slack_meetings_collection.update_one(
            {
                "huddle_id": huddle_id
            },
            {
                "$set": {
                    "embedding": embedding,
                    "processing_status": "completed",
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )

        logger.info(
            "[SLACK PIPELINE] Processing completed | huddle=%s",
            huddle_id
        )

    except Exception as e:

        _mark_failed(huddle_id, stage, e)


# ============================================================
# TRIGGER (public entry point)
# ============================================================

def trigger_slack_meeting_processing(huddle_id):
    """
    Atomically claim a slack_meetings document for processing
    and, if claimed, run the pipeline in a background thread.

    The atomic find_one_and_update both enforces the eligibility
    rule (status=ended, processing_status=pending, audio_file
    set) and prevents duplicate Slack event delivery from
    processing the same huddle twice: only the caller that
    successfully flips processing_status pending -> processing
    gets to run the pipeline. Every other caller (a duplicate
    "ended" event, or one that arrives after processing has
    already started/finished/failed) gets no match back and
    does nothing.
    """

    if not huddle_id:
        return

    claimed = slack_meetings_collection.find_one_and_update(
        {
            "huddle_id": huddle_id,
            "status": "ended",
            "processing_status": "pending",
            "audio_file": {
                "$nin": [None, ""]
            }
        },
        {
            "$set": {
                "processing_status": "processing",
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )

    if not claimed:

        logger.info(
            "[SLACK PIPELINE] Skipped | huddle=%s | "
            "not eligible (already processing/completed/"
            "failed, or no audio_file yet)",
            huddle_id
        )

        return

    threading.Thread(
        target=_run_pipeline,
        args=(claimed,),
        daemon=True,
        name=f"slack-pipeline-{huddle_id}"
    ).start()
