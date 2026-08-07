import os
import requests
from dotenv import load_dotenv

load_dotenv()

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")


def send_meeting_summary(
    meeting_title: str,
    summary: str,
    decisions,
    action_items,
    open_questions,
    filename: str,
):
    """
    Send formatted meeting summary to Slack.
    """

    if not SLACK_WEBHOOK_URL:
        print("Slack webhook not configured.")
        return

    # Convert list -> bullet points
    if isinstance(decisions, list):
        decisions = "\n".join(f"• {d}" for d in decisions)

    if isinstance(action_items, list):
        action_items = "\n".join(f"• {a}" for a in action_items)

    if isinstance(open_questions, list):
        open_questions = "\n".join(f"• {q}" for q in open_questions)

    # Default text if empty
    decisions = decisions or "No decisions found."
    action_items = action_items or "No action items found."
    open_questions = open_questions or "No open questions."

    message = f"""
🎙 *AI Meeting Intelligence Assistant*

━━━━━━━━━━━━━━━━━━━━━━

📁 *File*
{filename}

📝 *Meeting*
{meeting_title}

━━━━━━━━━━━━━━━━━━━━━━

📄 *Summary*
{summary}

━━━━━━━━━━━━━━━━━━━━━━

📌 *Decisions*
{decisions}

━━━━━━━━━━━━━━━━━━━━━━

✅ *Action Items*
{action_items}

━━━━━━━━━━━━━━━━━━━━━━

❓ *Open Questions*
{open_questions}

━━━━━━━━━━━━━━━━━━━━━━

🤖 _Generated automatically by AI Meeting Intelligence Assistant_
"""

    try:
        response = requests.post(
            SLACK_WEBHOOK_URL,
            json={"text": message},
            timeout=10,
        )

        if response.status_code != 200:
            print("Slack Error:", response.status_code)
            print(response.text)

    except Exception as e:
        print("Slack Exception:", e)