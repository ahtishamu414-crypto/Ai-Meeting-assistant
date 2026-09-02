from app.services.diarized_transcription import (
    transcribe_with_speakers
)


AUDIO_FILE = r"C:\Users\BN Com\Downloads\meeting1_clean.wav"


print("Starting combined transcription...\n")


results = transcribe_with_speakers(
    AUDIO_FILE
)


print("\n========== DIARIZED TRANSCRIPT ==========\n")


for item in results:

    start = item["start"]
    end = item["end"]
    speaker = item["speaker"]
    text = item["text"]

    print(
        f"[{start:.2f}s - {end:.2f}s] "
        f"{speaker}"
    )

    print(text)
    print()