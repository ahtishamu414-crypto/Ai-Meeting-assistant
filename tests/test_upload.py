import asyncio
import io
import os
import unittest

from fastapi import HTTPException, UploadFile

from app.api.upload import upload_audio


class UploadAudioTests(unittest.TestCase):
    def setUp(self):
        self.upload_dir = "uploads"
        os.makedirs(self.upload_dir, exist_ok=True)
        for entry in os.listdir(self.upload_dir):
            entry_path = os.path.join(self.upload_dir, entry)
            if os.path.isfile(entry_path):
                os.remove(entry_path)

    def test_accepts_audio_files(self):
        file = UploadFile(filename="meeting.mp3", file=io.BytesIO(b"fake audio"))
        response = asyncio.run(upload_audio(file))
        self.assertEqual(response["filename"], "meeting.mp3")
        self.assertTrue(os.path.exists(os.path.join(self.upload_dir, "meeting.mp3")))
        self.assertIn("transcript", response)
        self.assertIn("summary", response)

        transcript_path = os.path.join("transcripts", "meeting.txt")
        self.assertTrue(os.path.exists(transcript_path))

        summary_path = os.path.join("transcripts", "meeting.summary.txt")
        self.assertTrue(os.path.exists(summary_path))

    def test_rejects_non_audio_files(self):
        file = UploadFile(filename="notes.pdf", file=io.BytesIO(b"not audio"))
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(upload_audio(file))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertFalse(os.path.exists(os.path.join(self.upload_dir, "notes.pdf")))
