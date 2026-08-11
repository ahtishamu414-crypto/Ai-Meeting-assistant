import os
import requests
from dotenv import load_dotenv


load_dotenv()


SLACK_WEBHOOK_URL = os.getenv(
    "SLACK_WEBHOOK_URL"
)



def send_meeting_summary(
    meeting_title: str,
    summary: str,
    key_points,
    decisions,
    open_questions,
    action_items,
    filename: str,
):
    """
    Send formatted meeting summary to Slack.
    """


    if not SLACK_WEBHOOK_URL:

        print(
            "Slack webhook not configured."
        )

        return



    # Convert lists to bullets

    if isinstance(key_points, list):

        key_points = "\n".join(
            f"• {point}"
            for point in key_points
        )


    if isinstance(decisions, list):

        decisions = "\n".join(
            f"• {item}"
            for item in decisions
        )


    if isinstance(open_questions, list):

        open_questions = "\n".join(
            f"• {item}"
            for item in open_questions
        )


    if isinstance(action_items, list):

        formatted_actions = []

        for item in action_items:

            if isinstance(item, dict):

                formatted_actions.append(
                    f"• {item.get('task','')}"
                    f" | Owner: {item.get('owner','Not specified')}"
                    f" | Due: {item.get('due_date','Not specified')}"
                )

            else:

                formatted_actions.append(
                    f"• {item}"
                )


        action_items = "\n".join(
            formatted_actions
        )



    # Defaults

    key_points = (
        key_points
        or
        "No key points found."
    )


    decisions = (
        decisions
        or
        "No decisions found."
    )


    open_questions = (
        open_questions
        or
        "No open questions."
    )


    action_items = (
        action_items
        or
        "No action items found."
    )



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

📌 *Key Points*
{key_points}

━━━━━━━━━━━━━━━━━━━━━━

✅ *Decisions*
{decisions}

━━━━━━━━━━━━━━━━━━━━━━

📋 *Action Items*
{action_items}

━━━━━━━━━━━━━━━━━━━━━━

❓ *Open Questions*
{open_questions}

━━━━━━━━━━━━━━━━━━━━━━

🤖 Generated automatically by AI Meeting Intelligence Assistant
"""



    try:

        response = requests.post(
            SLACK_WEBHOOK_URL,
            json={
                "text": message
            },
            timeout=10,
        )


        if response.status_code != 200:

            print(
                "Slack Error:",
                response.status_code
            )

            print(
                response.text
            )

        else:

            print(
                "✅ Slack notification sent"
            )


    except Exception as e:

        print(
            "Slack Exception:",
            e
        )