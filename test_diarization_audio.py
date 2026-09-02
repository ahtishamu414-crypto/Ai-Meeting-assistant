import os
from dotenv import load_dotenv
from pyannote.audio import Pipeline

load_dotenv()

TOKEN = os.getenv("HUGGINGFACE_TOKEN")

AUDIO_FILE = r"C:\Users\BN Com\Downloads\meeting1_clean.wav"

print("Loading diarization pipeline...")

pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-3.1",
    token=TOKEN
)

print("Running speaker diarization...")

output = pipeline(AUDIO_FILE)

print("\n========== SPEAKER SEGMENTS ==========\n")

diarization = output.speaker_diarization

for turn, _, speaker in diarization.itertracks(yield_label=True):

    start = turn.start
    end = turn.end

    print(
        f"[{start:.2f}s - {end:.2f}s] "
        f"{speaker}"
    )

print("\n✅ Diarization completed successfully!")