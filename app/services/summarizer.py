import json
import re
import subprocess
from datetime import datetime, timedelta

import ollama


# ============================================================
# CLEAN LLM OUTPUT
# ============================================================

def clean_summary(text: str) -> str:
    """
    Remove ANSI escape sequences and markdown code blocks.
    """

    # Remove ANSI escape sequences
    text = re.sub(
        r"\x1B\[[0-?]*[ -/]*[@-~]",
        "",
        text,
    )

    text = text.strip()

    # Remove markdown JSON code blocks
    if text.startswith("```json"):
        text = text[7:]

    if text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


# ============================================================
# EMPTY SUMMARY
# ============================================================

def empty_summary():
    return {
        "meeting_title": "",
        "summary": "",
        "topics": [],
        "decisions": [],
        "open_questions": [],
        "key_points": [],
        "action_items": [],
    }


# ============================================================
# VALIDATE JSON
# ============================================================

def validate_json(data: dict) -> dict:
    """
    Ensure all required keys exist.
    """

    defaults = empty_summary()

    for key, value in defaults.items():
        data.setdefault(key, value)

    # Make sure action_items is a list
    if not isinstance(data["action_items"], list):
        data["action_items"] = []

    # Normalize action items
    normalized_actions = []

    for item in data["action_items"]:

        if not isinstance(item, dict):
            continue

        normalized_actions.append({
            "task": item.get(
                "task",
                "Not specified"
            ),
            "owner": item.get(
                "owner",
                "Not specified"
            ),
            "due_date": item.get(
                "due_date",
                "Not specified"
            ),
            "status": item.get(
                "status",
                "pending"
            ),
        })

    data["action_items"] = normalized_actions

    return data


# ============================================================
# NORMALIZE RELATIVE DATES
# ============================================================

def normalize_due_dates(data: dict) -> dict:
    """
    Convert relative dates such as Today, Tomorrow,
    Monday, Tuesday, etc. into YYYY-MM-DD.

    Example:

    Today    -> 2026-08-10
    Tomorrow -> 2026-08-11
    Wednesday -> 2026-08-12
    """

    today = datetime.now().date()

    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    for item in data.get("action_items", []):

        due_date = item.get("due_date")

        if not due_date:
            item["due_date"] = "Not specified"
            continue

        due_date = str(due_date).strip()

        if due_date.lower() in {
            "not specified",
            "none",
            "unknown",
            "n/a",
        }:
            item["due_date"] = "Not specified"
            continue

        # Already YYYY-MM-DD
        try:
            datetime.strptime(
                due_date,
                "%Y-%m-%d"
            )

            item["due_date"] = due_date
            continue

        except ValueError:
            pass

        # Today
        if due_date.lower() == "today":

            item["due_date"] = today.isoformat()
            continue

        # Tomorrow
        if due_date.lower() == "tomorrow":

            tomorrow = today + timedelta(days=1)

            item["due_date"] = tomorrow.isoformat()
            continue

        # Yesterday
        if due_date.lower() == "yesterday":

            yesterday = today - timedelta(days=1)

            item["due_date"] = yesterday.isoformat()
            continue

        # Weekday
        weekday_name = due_date.lower()

        if weekday_name in weekdays:

            target_day = weekdays[weekday_name]
            current_day = today.weekday()

            days_ahead = (
                target_day - current_day
            ) % 7

            # If same weekday, assume next occurrence
            if days_ahead == 0:
                days_ahead = 7

            target_date = today + timedelta(
                days=days_ahead
            )

            item["due_date"] = target_date.isoformat()

            continue

        # Unknown format
        item["due_date"] = due_date

    return data


# ============================================================
# SUMMARIZE MEETING
# ============================================================

def summarize_text(
    text: str,
    model: str = "llama3.2:3b",
):
    """
    Analyze meeting transcript and return structured JSON.
    """

    today = datetime.now().date()

    prompt = f"""
You are an AI Meeting Intelligence Assistant.

Today's date is:

{today.isoformat()}

Analyze the following transcript.

Return ONLY valid JSON.

Do NOT use markdown.
Do NOT explain anything.
Do NOT write extra text.

Use exactly this schema:

{{
    "meeting_title": "",
    "summary": "",
    "topics": [],
    "decisions": [],
    "open_questions": [],
    "key_points": [],
    "action_items": [
        {{
            "task": "",
            "owner": "",
            "due_date": "",
            "status": "pending"
        }}
    ]
}}

RULES

meeting_title:
- Create a short descriptive title.

summary:
- Write 2-3 concise sentences.
- Only summarize information actually present in the transcript.

topics:
- Extract the main discussion topics.

decisions:
- Extract ONLY confirmed decisions.
- Do not treat suggestions as decisions.

open_questions:
- Extract unresolved questions.

key_points:
- List the most important discussion points.

action_items:
- Only include tasks explicitly assigned to someone.
- Never invent tasks.
- Never invent owners.
- Never invent due dates.
- Every action item must contain:
  task
  owner
  due_date
  status

owner:
- If an owner is not explicitly mentioned, use:
  "Not specified"

due_date:
- If no due date is mentioned, use:
  "Not specified"

IMPORTANT DATE RULES:

Today's date is:
{today.isoformat()}

Convert relative dates into actual dates.

Examples:

"today" -> {today.isoformat()}

"tomorrow" -> calculate tomorrow's date.

"Monday", "Tuesday", "Wednesday", etc.
-> calculate the next occurrence of that weekday.

Return due_date in this format whenever possible:

YYYY-MM-DD

Do NOT return:
"Wednesday"
"Friday"
"Tomorrow"

Return the actual date instead.

STATUS:

Every newly extracted action item must have:

"status": "pending"

NON-MEETING CONTENT:

If the transcript is NOT a business meeting, interview,
classroom discussion, or project discussion:

- Set an appropriate meeting_title.
- Do not invent action items.
- Return:
  "action_items": []
- Summarize only what actually happened.

Transcript:

{text}
"""

    # ========================================================
    # METHOD 1 - OLLAMA PYTHON API
    # ========================================================

    try:

        response = ollama.chat(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            format="json",
            options={
                "temperature": 0,
            },
        )

        output = clean_summary(
            response["message"]["content"]
        )

        data = json.loads(output)

        data = validate_json(data)

        data = normalize_due_dates(data)

        return data

    except json.JSONDecodeError:

        print(
            "Invalid JSON returned by Ollama."
        )

    except Exception as e:

        print(
            "Ollama Python Error:",
            e
        )

    # ========================================================
    # METHOD 2 - OLLAMA CLI
    # ========================================================

    try:

        process = subprocess.run(
            [
                "ollama",
                "run",
                model,
            ],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if process.returncode == 0:

            output = clean_summary(
                process.stdout
            )

            try:

                data = json.loads(output)

                data = validate_json(data)

                data = normalize_due_dates(data)

                return data

            except json.JSONDecodeError:

                print(
                    "CLI returned invalid JSON."
                )

        else:

            print(process.stderr)

    except FileNotFoundError:

        print(
            "Ollama CLI not installed."
        )

    except Exception as e:

        print(
            "Ollama CLI Error:",
            e
        )

    return empty_summary()