import os
import subprocess
import tempfile

import whisper

from dotenv import load_dotenv
from pyannote.audio import Pipeline

load_dotenv()

HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

MODEL_NAME = "small"

whisper_model = None
diarization_pipeline = None


# ============================================================
# LOAD MODELS
# ============================================================

def get_models():

    global whisper_model
    global diarization_pipeline

    # --------------------------------------------------------
    # WHISPER
    # --------------------------------------------------------

    if whisper_model is None:

        print("Loading Whisper model...")

        whisper_model = whisper.load_model(
            MODEL_NAME
        )

        print("✅ Whisper model loaded")

    # --------------------------------------------------------
    # PYANNOTE
    # --------------------------------------------------------

    if diarization_pipeline is None:

        if not HF_TOKEN:

            raise RuntimeError(
                "HUGGINGFACE_TOKEN is not configured in .env"
            )

        print(
            "Loading speaker diarization model..."
        )

        diarization_pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=HF_TOKEN
        )

        print(
            "✅ Speaker diarization model loaded"
        )


# ============================================================
# CONVERT AUDIO TO CLEAN WAV
# ============================================================

def convert_to_clean_wav(
    input_file: str
) -> str:

    """
    Convert uploaded audio to a standardized WAV file.

    Output:
        16 kHz
        mono
        PCM 16-bit

    This prevents MP3 decoding/sample-count problems
    with pyannote.
    """

    temp_dir = tempfile.gettempdir()

    output_file = os.path.join(
        temp_dir,
        f"meeting_clean_{os.getpid()}.wav"
    )

    print(
        "🔄 Converting audio to clean WAV..."
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        input_file,
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        output_file
    ]

    try:

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:

            print(
                result.stderr
            )

            raise RuntimeError(
                "FFmpeg failed to convert audio."
            )

        if not os.path.exists(output_file):

            raise RuntimeError(
                "FFmpeg did not create the output WAV file."
            )

        print(
            f"✅ Clean WAV created: {output_file}"
        )

        return output_file

    except FileNotFoundError:

        raise RuntimeError(
            "FFmpeg was not found. "
            "Make sure ffmpeg is available in PATH."
        )


# ============================================================
# TIMESTAMP
# ============================================================

def format_timestamp(
    seconds: float
) -> str:

    minutes = int(
        seconds // 60
    )

    seconds = int(
        seconds % 60
    )

    return f"{minutes:02}:{seconds:02}"


# ============================================================
# FIND SPEAKER
# ============================================================

def get_speaker_at_time(
    diarization,
    start,
    end
):

    speaker_times = {}

    for turn, _, speaker in diarization.itertracks(
        yield_label=True
    ):

        overlap_start = max(
            start,
            turn.start
        )

        overlap_end = min(
            end,
            turn.end
        )

        overlap = max(
            0,
            overlap_end - overlap_start
        )

        if overlap > 0:

            speaker_times[speaker] = (
                speaker_times.get(
                    speaker,
                    0
                )
                + overlap
            )

    if not speaker_times:

        return "UNKNOWN"

    return max(
        speaker_times,
        key=speaker_times.get
    )


# ============================================================
# TRANSCRIBE AUDIO
# ============================================================

def transcribe_audio(
    file_path: str
) -> str:

    if not os.path.exists(file_path):

        raise FileNotFoundError(
            f"Audio file not found: {file_path}"
        )

    clean_wav = None

    try:

        # ====================================================
        # LOAD MODELS
        # ====================================================

        get_models()

        # ====================================================
        # CONVERT AUDIO
        # ====================================================

        clean_wav = convert_to_clean_wav(
            file_path
        )

        # ====================================================
        # WHISPER
        # ====================================================

        print(
            "🎧 Transcribing audio..."
        )

        result = whisper_model.transcribe(
            clean_wav,
            temperature=0,
            fp16=False
        )

        # ====================================================
        # PYANNOTE
        # ====================================================

        print(
            "🗣 Running speaker diarization..."
        )

        output = diarization_pipeline(
            clean_wav
        )

        # ====================================================
        # HANDLE PYANNOTE OUTPUT
        # ====================================================

        if hasattr(
            output,
            "speaker_diarization"
        ):

            diarization = (
                output.speaker_diarization
            )

        else:

            diarization = output

        # ====================================================
        # COMBINE WHISPER + SPEAKERS
        # ====================================================

        transcript = []

        for segment in result.get(
            "segments",
            []
        ):

            start = segment["start"]

            end = segment["end"]

            text = segment["text"].strip()

            if not text:

                continue

            speaker = get_speaker_at_time(
                diarization,
                start,
                end
            )

            start_time = format_timestamp(
                start
            )

            end_time = format_timestamp(
                end
            )

            transcript.append(
                f"[{start_time} - {end_time}] "
                f"{speaker}\n"
                f"{text}\n"
            )

        final_transcript = "\n".join(
            transcript
        )

        if not final_transcript:

            return (
                "No speech detected in audio."
            )

        print(
            "✅ Speaker-labeled transcription completed"
        )

        return final_transcript

    except Exception as e:

        print(
            "❌ Transcription error:",
            e
        )

        raise

    finally:

        # ====================================================
        # DELETE TEMPORARY WAV
        # ====================================================

        if clean_wav:

            try:

                if os.path.exists(
                    clean_wav
                ):

                    os.remove(
                        clean_wav
                    )

                    print(
                        "🗑 Temporary WAV removed"
                    )

            except Exception as cleanup_error:

                print(
                    "⚠️ Could not remove temporary WAV:",
                    cleanup_error
                )