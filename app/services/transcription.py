import os
from dotenv import load_dotenv

try:
    import whisper
except Exception:  # pragma: no cover - depends on local environment
    whisper = None

load_dotenv()

MODEL_NAME = "small"
model = whisper.load_model(MODEL_NAME) if whisper is not None else None


def transcribe_audio(file_path: str) -> str:
    """
    Converts an audio file into text using a local Whisper model when available.

    Args:
        file_path: Path to the uploaded audio file.

    Returns:
        Transcript as text.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    if model is None:
        return "Transcription unavailable: local Whisper model is not available in this environment"

    try:
        result = model.transcribe(file_path, temperature=0,language="en", fp16=False)
        return result.get("text", "")
    except Exception as exc:
        return f"Transcription unavailable: {exc}"