import whisper
from pyannote.audio import Pipeline
from dotenv import load_dotenv
import os

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")

WHISPER_MODEL = "small"

whisper_model = None
diarization_pipeline = None


def get_models():

    global whisper_model
    global diarization_pipeline

    if whisper_model is None:
        print("Loading Whisper...")
        whisper_model = whisper.load_model(WHISPER_MODEL)
        print("✅ Whisper loaded")

    if diarization_pipeline is None:
        print("Loading speaker diarization...")

        diarization_pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=HF_TOKEN
        )

        print("✅ Diarization loaded")


def get_speaker_at_time(diarization, start, end):

    speaker_times = {}

    for turn, _, speaker in diarization.itertracks(
        yield_label=True
    ):

        overlap_start = max(start, turn.start)
        overlap_end = min(end, turn.end)

        overlap = max(
            0,
            overlap_end - overlap_start
        )

        if overlap > 0:

            speaker_times[speaker] = (
                speaker_times.get(speaker, 0)
                + overlap
            )

    if not speaker_times:
        return "UNKNOWN"

    return max(
        speaker_times,
        key=speaker_times.get
    )


def format_timestamp(seconds):

    minutes = int(seconds // 60)
    seconds = int(seconds % 60)

    return f"{minutes:02}:{seconds:02}"


def transcribe_with_speakers(file_path):

    get_models()

    print("🎧 Running Whisper...")

    result = whisper_model.transcribe(
        file_path,
        temperature=0,
        fp16=False
    )

    print("🗣 Running speaker diarization...")

    output = diarization_pipeline(file_path)

    # Newer pyannote versions may return DiarizeOutput
    if hasattr(output, "speaker_diarization"):
        diarization = output.speaker_diarization
    else:
        diarization = output

    final_transcript = []

    for segment in result.get("segments", []):

        start = segment["start"]
        end = segment["end"]

        text = segment["text"].strip()

        speaker = get_speaker_at_time(
            diarization,
            start,
            end
        )

        final_transcript.append(
            {
                "start": start,
                "end": end,
                "speaker": speaker,
                "text": text
            }
        )

    return final_transcript