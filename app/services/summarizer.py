import json
import re
import subprocess

import ollama


def clean_summary(text: str) -> str:
    """
    Remove ANSI escape sequences and markdown.
    """

    text = re.sub(
        r"\x1B\[[0-?]*[ -/]*[@-~]",
        "",
        text,
    )

    text = text.strip()

    if text.startswith("```json"):
        text = text.replace("```json", "").replace("```", "")

    elif text.startswith("```"):
        text = text.replace("```", "")

    return text.strip()


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


def validate_json(data: dict) -> dict:
    """
    Ensure all required keys exist.
    """

    defaults = empty_summary()

    for key, value in defaults.items():
        data.setdefault(key, value)

    return data


def summarize_text(
    text: str,
    model: str = "llama3.2:3b",
):
    """
    Analyze meeting transcript and return structured JSON.
    """

    prompt = f"""
You are an AI Meeting Intelligence Assistant.

Analyze the following meeting transcript.

Return ONLY valid JSON.

Do NOT use markdown.
Do NOT explain anything.
Do NOT write any extra text.

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
            "due_date": ""
        }}
    ]
}}

Rules:

meeting_title
- Create a short descriptive title.

summary
- Write 2-3 concise sentences.

topics
- Extract the discussion topics.

decisions
- Extract only confirmed decisions.

open_questions
- Extract unresolved questions.

key_points
- List the most important discussion points.

action_items
- Only include tasks that were explicitly assigned.
- Never invent owners.
- Never invent due dates.
- If owner is missing use:
  "Not specified"
- If due date is missing use:
  "Not specified"

Transcript:

{text}
"""

    # ----------------------------
    # Method 1 - Python API
    # ----------------------------

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

        return validate_json(data)

    except json.JSONDecodeError:
        print("Invalid JSON returned by Ollama.")

    except Exception as e:
        print("Ollama Python Error:", e)

    # ----------------------------
    # Method 2 - CLI
    # ----------------------------

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

            output = clean_summary(process.stdout)

            try:
                data = json.loads(output)

                return validate_json(data)

            except json.JSONDecodeError:
                print("CLI returned invalid JSON.")

        else:
            print(process.stderr)

    except FileNotFoundError:
        print("Ollama CLI not installed.")

    except Exception as e:
        print("Ollama CLI Error:", e)

    return empty_summary()