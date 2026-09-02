"""
Tests that the Slack notification step in _run_pipeline
(app/services/slack_pipeline.py) is correctly isolated from
processing_status: a notification failure must never turn an
otherwise-successful "completed" meeting into "failed".

All external dependencies (Mongo, transcription, summarizer,
embedding, Jira, Slack) are mocked - no real audio, model, or
network calls are made.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services import slack_pipeline


def make_claimed_meeting(tmp_path):
    audio_file = tmp_path / "huddle.wav"
    audio_file.write_bytes(b"fake-audio")

    return {
        "huddle_id": "H1",
        "audio_file": str(audio_file),
    }


@patch.object(slack_pipeline, "send_meeting_summary_to_participants")
@patch.object(slack_pipeline, "create_meeting_embedding")
@patch.object(slack_pipeline, "create_jira_issue")
@patch.object(slack_pipeline, "summarize_text")
@patch.object(slack_pipeline, "transcribe_audio")
@patch.object(slack_pipeline, "slack_meetings_collection")
def test_notification_failure_does_not_flip_completed_to_failed(
    mock_collection,
    mock_transcribe,
    mock_summarize,
    mock_jira,
    mock_embedding,
    mock_notify,
    tmp_path,
):
    mock_transcribe.return_value = "hello world"
    mock_summarize.return_value = {
        "meeting_title": "Test Meeting",
        "summary": "A summary.",
        "topics": [],
        "decisions": [],
        "open_questions": [],
        "key_points": [],
        "action_items": [],
    }
    mock_embedding.return_value = [0.0] * 384

    # find_one for the post-completion re-fetch inside the
    # notification step.
    mock_collection.find_one.return_value = {
        "huddle_id": "H1",
        "processing_status": "completed",
        "participants": ["U1"],
    }

    # The notification step must never raise out of
    # send_meeting_summary_to_participants for this test to be
    # meaningful - simulate it blowing up internally anyway,
    # to prove _run_pipeline's own try/except also protects it.
    mock_notify.side_effect = RuntimeError("Slack is down")

    meeting = make_claimed_meeting(tmp_path)

    slack_pipeline._run_pipeline(meeting)

    # Find the update_one call that set processing_status.
    completed_calls = [
        call
        for call in mock_collection.update_one.call_args_list
        if "processing_status" in call.args[1].get("$set", {})
    ]

    assert completed_calls, "expected a processing_status update"

    last_status_call = completed_calls[-1]
    assert last_status_call.args[1]["$set"]["processing_status"] == "completed"

    # Notification was attempted exactly once, and its failure
    # must not have triggered a second update_one flipping
    # status to "failed".
    assert mock_notify.called
    assert all(
        call.args[1].get("$set", {}).get("processing_status") != "failed"
        for call in mock_collection.update_one.call_args_list
    )


@patch.object(slack_pipeline, "send_meeting_summary_to_participants")
@patch.object(slack_pipeline, "create_meeting_embedding")
@patch.object(slack_pipeline, "create_jira_issue")
@patch.object(slack_pipeline, "summarize_text")
@patch.object(slack_pipeline, "transcribe_audio")
@patch.object(slack_pipeline, "slack_meetings_collection")
def test_jira_key_persisted_onto_action_items(
    mock_collection,
    mock_transcribe,
    mock_summarize,
    mock_jira,
    mock_embedding,
    mock_notify,
    tmp_path,
):
    mock_transcribe.return_value = "hello world"
    mock_summarize.return_value = {
        "meeting_title": "Test Meeting",
        "summary": "A summary.",
        "topics": [],
        "decisions": [],
        "open_questions": [],
        "key_points": [],
        "action_items": [
            {"task": "Do the thing", "owner": "Ali", "due_date": "Tomorrow"}
        ],
    }
    mock_jira.return_value = {"key": "PROJ-7"}
    mock_embedding.return_value = [0.0] * 384
    mock_collection.find_one.return_value = {
        "huddle_id": "H1",
        "processing_status": "completed",
        "participants": [],
    }

    meeting = make_claimed_meeting(tmp_path)

    slack_pipeline._run_pipeline(meeting)

    action_item_calls = [
        call
        for call in mock_collection.update_one.call_args_list
        if "action_items" in call.args[1].get("$set", {})
    ]

    assert action_item_calls, "expected an action_items update"

    saved_items = action_item_calls[-1].args[1]["$set"]["action_items"]
    assert saved_items[0]["jira_key"] == "PROJ-7"
