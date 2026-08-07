import re
import ollama


def clean_text(text: str) -> str:
    """
    Remove extra whitespace.
    """
    return " ".join(text.split())


def extract_action_items(text: str, model: str = "llama3.2:3b") -> str:
    """
    Extract only real action items from a meeting transcript.
    """

    prompt = f"""
You are an AI Meeting Assistant.

Your task is ONLY to extract action items that are EXPLICITLY mentioned in the transcript.

An action item is a task assigned or agreed upon by someone.

Examples:
✓ Ali will send the report tomorrow.
✓ Sara should prepare the presentation.
✓ John needs to email the client.
✓ Ahmed will schedule the next meeting.

Do NOT extract:
- greetings
- introductions
- casual conversation
- food or drink requests
- questions
- opinions
- jokes
- arguments
- movie dialogue
- profanity
- threats
- emotional discussions
- assumptions
- implied tasks

IMPORTANT:
- NEVER invent tasks.
- NEVER guess.
- If there are NO action items, return EXACTLY:

No action items found.

Return ONLY the action items.
Do not explain anything.

Transcript:
{text}
"""

    try:
        response = ollama.chat(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        action_items = response["message"]["content"]

        return clean_text(action_items)

    except Exception as e:
        return f"Action item extraction failed: {e}"