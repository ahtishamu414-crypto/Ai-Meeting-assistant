import re
import subprocess


def clean_summary(text: str) -> str:
    """
    Remove ANSI escape sequences and extra whitespace.
    """
    # Remove terminal escape codes
    text = re.sub(r"\x1B\[[0-?]*[ -/]*[@-~]", "", text)

    # Remove multiple spaces/newlines
    text = " ".join(text.split())

    return text


def summarize_text(text: str, model: str = "llama3.2:3b") -> str:
    """
    Summarize a meeting transcript using Ollama.

    It first tries the Python Ollama package.
    If that fails, it falls back to the Ollama CLI.
    """

    prompt = f"""
You are an AI Meeting Assistant.

Summarize ONLY the information explicitly mentioned in the transcript.

Rules:
- Do not invent names or facts.
- Do not assume context.
- Keep the summary between 3 and 5 sentences.
- Return plain text only.

Transcript:
{text}
"""

    # -----------------------------
    # Try Python Ollama package
    # -----------------------------
    try:
        import ollama

        response = ollama.chat(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        summary = response["message"]["content"]
        return clean_summary(summary)

    except Exception:
        pass

    # -----------------------------
    # Fallback to Ollama CLI
    # -----------------------------
    try:
        proc = subprocess.run(
            ["ollama", "run", model],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if proc.returncode == 0:
            return clean_summary(proc.stdout)

        return f"Ollama CLI error: {proc.stderr.strip()}"

    except FileNotFoundError:
        return "Summarization unavailable: Ollama is not installed."

    except Exception as exc:
        return f"Summarization unavailable: {exc}"