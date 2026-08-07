import pathlib
import wave
import struct
import requests

root = pathlib.Path(__file__).resolve().parents[1]
path = root / 'scripts' / 'test_upload.wav'
path.parent.mkdir(exist_ok=True)
with wave.open(str(path), 'wb') as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(16000)
    frames = struct.pack('<' + 'h' * 16000, *([0] * 16000))
    w.writeframes(frames)

with open(path, 'rb') as f:
    files = {'file': ('test_upload.wav', f, 'audio/wav')}
    resp = requests.post('http://127.0.0.1:8000/upload', files=files, timeout=180)
    print(resp.status_code)
    print(resp.text)
