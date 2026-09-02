import os
from dotenv import load_dotenv
from pyannote.audio import Pipeline

load_dotenv()

token = os.getenv("HUGGINGFACE_TOKEN")

if not token:
    raise RuntimeError("HUGGINGFACE_TOKEN not found in .env")

print("Loading speaker diarization model...")

pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-3.1",
    token=token
)

print("✅ Speaker diarization model loaded successfully!")