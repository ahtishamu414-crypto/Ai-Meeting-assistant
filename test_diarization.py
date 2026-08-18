from app.services.diarization import diarize_audio

result = diarize_audio("uploads/The Irishman - Al Pacino Says You're Late Clip  Netflix.mp3")

for r in result:
    print(r)