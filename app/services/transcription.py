import os
from dotenv import load_dotenv

load_dotenv()

try:
    import whisper
    print("✅ Whisper imported successfully")
except Exception as e:
    print("❌ Whisper import failed:", e)
    whisper = None


MODEL_NAME = "small"

model = None


def get_whisper_model():
    """
    Load Whisper model only when needed.
    """
    global model

    if model is None:
        if whisper is None:
            raise RuntimeError(
                "Whisper package is not available"
            )

        try:
            print(f"Loading Whisper model: {MODEL_NAME}")
            model = whisper.load_model(MODEL_NAME)
            print("✅ Whisper model loaded successfully")

        except Exception as e:
            print("❌ Whisper model loading failed:", e)
            raise e

    return model


def format_timestamp(seconds: float) -> str:
    """
    Convert seconds into MM:SS format.
    Example:
    65.4 -> 01:05
    """
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)

    return f"{minutes:02}:{seconds:02}"


def transcribe_audio(file_path: str) -> str:
    """
    Transcribe audio using Whisper and return timestamped transcript.
    """

    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"Audio file not found: {file_path}"
        )

    try:
        whisper_model = get_whisper_model()

        print("🎧 Transcribing audio...")

        result = whisper_model.transcribe(
            file_path,
            temperature=0,
            fp16=False
        )

        transcript = []

        for segment in result.get("segments", []):

            start = format_timestamp(
                segment["start"]
            )

            end = format_timestamp(
                segment["end"]
            )

            text = segment["text"].strip()

            transcript.append(
                f"[{start} - {end}]\n{text}\n"
            )

        final_transcript = "\n".join(transcript)

        if not final_transcript:
            return "No speech detected in audio."

        return final_transcript


    except Exception as e:
        print("❌ Transcription error:", e)

        return (
            f"Transcription failed: {str(e)}"
        )