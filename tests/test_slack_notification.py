"""
Tests for app.services.slack_notification.

These tests never call the real Slack API or a real MongoDB -
the Slack client and the slack_meetings collection are mocked.
"""

from unittest.mock import MagicMock, patch

import pytest
from slack_sdk.errors import SlackApiError

from app.services import slack_notification as notif


def make_meeting(**overrides):
    meeting = {
        "huddle_id": "H1",
        "meeting_title": "Weekly Sync",
        "summary": "We discussed progress.",
        "key_points": ["Point A"],
        "action_items": [
            {"task": "Do X", "owner": "Ali", "due_date": "Tomorrow"}
        ],
        "decisions": [],
        "open_questions": [],
        "participants": ["U1"],
        "notifications": {},
    }
    meeting.update(overrides)
    return meeting


@pytest.fixture(autouse=True)
def fake_slack_client():
    """
    Replace the module-level Slack client with a MagicMock so no
    real network/Slack call is ever made, and reset the lazy
    singleton between tests.
    """

    notif._client = None

    client = MagicMock()
    client.conversations_open.return_value = {"channel": {"id": "D1"}}
    client.chat_postMessage.return_value = {"ok": True}

    with patch.object(notif, "_get_client", return_value=client):
        yield client

    notif._client = None


@pytest.fixture(autouse=True)
def fake_collection():
    with patch.object(notif, "slack_meetings_collection") as collection:
        yield collection


# ============================================================
# 1. ONE PARTICIPANT
# ============================================================

def test_single_participant_receives_notification(fake_slack_client, fake_collection):
    meeting = make_meeting(participants=["U1"])

    notif.send_meeting_summary_to_participants(meeting)

    fake_slack_client.conversations_open.assert_called_once_with(users=["U1"])
    fake_slack_client.chat_postMessage.assert_called_once()
    assert fake_collection.update_one.called

    set_fields = fake_collection.update_one.call_args[0][1]["$set"]
    assert set_fields["notifications.U1"]["status"] == "sent"
    assert set_fields["notification_status"] == "sent"


# ============================================================
# 2. MULTIPLE PARTICIPANTS
# ============================================================

def test_multiple_participants_all_receive_notification(fake_slack_client, fake_collection):
    meeting = make_meeting(participants=["U1", "U2", "U3"])

    notif.send_meeting_summary_to_participants(meeting)

    assert fake_slack_client.conversations_open.call_count == 3
    assert fake_slack_client.chat_postMessage.call_count == 3

    set_fields = fake_collection.update_one.call_args[0][1]["$set"]
    assert set_fields["notification_status"] == "sent"
    for uid in ("U1", "U2", "U3"):
        assert set_fields[f"notifications.{uid}"]["status"] == "sent"


# ============================================================
# 3. DUPLICATE PARTICIPANT IDS
# ============================================================

def test_duplicate_participant_ids_are_deduped(fake_slack_client, fake_collection):
    meeting = make_meeting(participants=["U1", "U1", "U1"])

    notif.send_meeting_summary_to_participants(meeting)

    fake_slack_client.conversations_open.assert_called_once_with(users=["U1"])


# ============================================================
# 4. EMPTY PARTICIPANTS
# ============================================================

def test_empty_participants_does_not_crash_or_call_slack(fake_slack_client, fake_collection):
    meeting = make_meeting(participants=[])

    notif.send_meeting_summary_to_participants(meeting)

    fake_slack_client.conversations_open.assert_not_called()
    fake_collection.update_one.assert_not_called()


# ============================================================
# 5. SLACK API FAILURE DOES NOT RAISE
# ============================================================

def test_slack_api_failure_is_caught_and_recorded(fake_slack_client, fake_collection):
    fake_slack_client.conversations_open.side_effect = SlackApiError(
        message="user_not_found",
        response={"error": "user_not_found"},
    )

    meeting = make_meeting(participants=["U1"])

    # Must not raise.
    notif.send_meeting_summary_to_participants(meeting)

    set_fields = fake_collection.update_one.call_args[0][1]["$set"]
    assert set_fields["notifications.U1"]["status"] == "failed"
    assert set_fields["notification_status"] == "failed"


def test_partial_failure_marks_rollup_partial(fake_slack_client, fake_collection):
    def conversations_open(users):
        if users == ["U1"]:
            return {"channel": {"id": "D1"}}
        raise SlackApiError(message="fail", response={"error": "channel_not_found"})

    fake_slack_client.conversations_open.side_effect = conversations_open

    meeting = make_meeting(participants=["U1", "U2"])

    notif.send_meeting_summary_to_participants(meeting)

    set_fields = fake_collection.update_one.call_args[0][1]["$set"]
    assert set_fields["notifications.U1"]["status"] == "sent"
    assert set_fields["notifications.U2"]["status"] == "failed"
    assert set_fields["notification_status"] == "partial"


# ============================================================
# 6. IDEMPOTENCY / DUPLICATE PIPELINE INVOCATION
# ============================================================

def test_already_notified_participant_is_skipped(fake_slack_client, fake_collection):
    meeting = make_meeting(
        participants=["U1"],
        notifications={"U1": {"status": "sent", "sent_at": "2026-01-01"}},
    )

    notif.send_meeting_summary_to_participants(meeting)

    fake_slack_client.conversations_open.assert_not_called()
    fake_collection.update_one.assert_not_called()


def test_mixed_already_sent_and_new_participants(fake_slack_client, fake_collection):
    meeting = make_meeting(
        participants=["U1", "U2"],
        notifications={"U1": {"status": "sent"}},
    )

    notif.send_meeting_summary_to_participants(meeting)

    fake_slack_client.conversations_open.assert_called_once_with(users=["U2"])

    set_fields = fake_collection.update_one.call_args[0][1]["$set"]
    assert "notifications.U1" not in set_fields
    assert set_fields["notifications.U2"]["status"] == "sent"
    # U1 already sent + U2 sent now => full rollup "sent"
    assert set_fields["notification_status"] == "sent"


# ============================================================
# 7. MISSING SUMMARY FIELDS DO NOT CRASH
# ============================================================

def test_missing_summary_fields_do_not_crash(fake_slack_client, fake_collection):
    meeting = {"huddle_id": "H1", "participants": ["U1"]}

    notif.send_meeting_summary_to_participants(meeting)

    fake_slack_client.chat_postMessage.assert_called_once()
    text = fake_slack_client.chat_postMessage.call_args.kwargs["text"]
    assert "Meeting Summary" in text
    assert "Slack Huddle" in text


# ============================================================
# 8. JIRA KEY INCLUDED WHEN AVAILABLE
# ============================================================

def test_jira_key_included_in_message(fake_slack_client, fake_collection):
    meeting = make_meeting(
        participants=["U1"],
        action_items=[
            {"task": "Do X", "owner": "Ali", "due_date": "Tomorrow", "jira_key": "PROJ-42"}
        ],
    )

    notif.send_meeting_summary_to_participants(meeting)

    text = fake_slack_client.chat_postMessage.call_args.kwargs["text"]
    assert "PROJ-42" in text
    assert "*Jira:*" in text


def test_no_jira_section_when_no_key(fake_slack_client, fake_collection):
    meeting = make_meeting(participants=["U1"])

    notif.send_meeting_summary_to_participants(meeting)

    text = fake_slack_client.chat_postMessage.call_args.kwargs["text"]
    assert "*Jira:*" not in text


# ============================================================
# 9. NO SECRETS LOGGED
# ============================================================

def test_no_token_logged(fake_slack_client, fake_collection, caplog):
    with patch.object(notif, "SLACK_BOT_TOKEN", "xoxb-super-secret-token"):

        meeting = make_meeting(participants=["U1"])

        with caplog.at_level("INFO"):
            notif.send_meeting_summary_to_participants(meeting)

        assert "xoxb-super-secret-token" not in caplog.text


# ============================================================
# MISSING TOKEN DOES NOT CRASH
# ============================================================

def test_missing_token_skips_without_crashing(fake_collection):
    with patch.object(notif, "_get_client", return_value=None):

        meeting = make_meeting(participants=["U1"])

        notif.send_meeting_summary_to_participants(meeting)

    fake_collection.update_one.assert_not_called()


# ============================================================
# MALFORMED MEETING DATA
# ============================================================

def test_non_dict_meeting_does_not_crash(fake_slack_client, fake_collection):
    notif.send_meeting_summary_to_participants(None)  # type: ignore[arg-type]

    fake_slack_client.conversations_open.assert_not_called()
