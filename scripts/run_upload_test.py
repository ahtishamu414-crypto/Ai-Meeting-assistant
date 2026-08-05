import pathlib
import wave
import struct
import uuid
import urllib.request

root = pathlib.Path(__file__).resolve().parents[1]
path = root / 'scripts' / 'test_upload.wav'
path.parent.mkdir(exist_ok=True)
with wave.open(str(path), 'wb') as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(16000)
    frames = struct.pack('<' + 'h' * 16000, *([0] * 16000))
    w.writeframes(frames)

boundary = '----WebKitFormBoundary' + uuid.uuid4().hex
body = []
body.append(f'--{boundary}')
body.append('Content-Disposition: form-data; name="file"; filename="test_upload.wav"')
body.append('Content-Type: audio/wav')
body.append('')
body_bytes = '\r\n'.join(body).encode('utf-8') + b'\r\n' + path.read_bytes() + b'\r\n' + f'--{boundary}--\r\n'.encode('utf-8')
req = urllib.request.Request(
    'http://127.0.0.1:8000/upload',
    data=body_bytes,
    method='POST',
)
req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
req.add_header('Accept', 'application/json')
with urllib.request.urlopen(req, timeout=120) as resp:
    print(resp.status)
    print(resp.read().decode('utf-8'))
