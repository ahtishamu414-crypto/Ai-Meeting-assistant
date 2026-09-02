from app.services.transcription import transcribe_audio


AUDIO_FILE = r"C:\Users\BN Com\Downloads\meeting1_clean.wav"


print("Starting transcription...\n")


transcript = transcribe_audio(
    AUDIO_FILE
)


print("\n========== FINAL TRANSCRIPT ==========\n")

print(transcript)