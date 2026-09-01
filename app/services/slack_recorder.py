import logging
import os
import threading
import time
import wave

import numpy as np
import soundcard as sc


logger = logging.getLogger("slack_recorder")


# ============================================================
# CONFIGURATION
# ============================================================

SAMPLE_RATE = 48000
CHANNELS = 2
CHUNK_SECONDS = 0.1

RECORDINGS_DIR = "recordings"


# ============================================================
# ACTIVE RECORDINGS
# ============================================================

_active_recordings = {}


# ============================================================
# RECORDER CLASS
# ============================================================

class SlackRecorder:

    def __init__(self, huddle_id: str):
        self.huddle_id = huddle_id
        self.recording = False
        self.thread = None
        self.audio_chunks = []

        self.microphone = None
        self.loopback = None

        self.output_path = None

    # --------------------------------------------------------
    # FIND DEVICES
    # --------------------------------------------------------

    def _find_devices(self):
        """
        Find the microphone and system-audio loopback device.
        """

        microphones = sc.all_microphones(include_loopback=False)
        speakers = sc.all_speakers()

        if not microphones:
            raise RuntimeError("No microphone found.")

        if not speakers:
            raise RuntimeError("No speaker found.")

        # Prefer the Realtek microphone used during testing.
        self.microphone = next(
            (
                m for m in microphones
                if "Microphone Array" in m.name
            ),
            microphones[0],
        )

        # Prefer the headphones loopback used during testing.
        speaker = next(
            (
                s for s in speakers
                if "Headphones" in s.name
            ),
            speakers[0],
        )

        self.loopback = sc.get_microphone(
            speaker.name,
            include_loopback=True
        )

        logger.info(
            "Recorder devices selected | MIC=%s | LOOPBACK=%s",
            self.microphone.name,
            self.loopback.name,
        )

    # --------------------------------------------------------
    # START
    # --------------------------------------------------------

    def start(self):
        """
        Start recording microphone + system audio.
        """

        if self.recording:
            logger.warning(
                "Recording already running | huddle_id=%s",
                self.huddle_id
            )
            return

        self._find_devices()

        os.makedirs(RECORDINGS_DIR, exist_ok=True)

        safe_huddle_id = str(self.huddle_id).replace("/", "_")

        self.output_path = os.path.join(
            RECORDINGS_DIR,
            f"slack_huddle_{safe_huddle_id}.wav"
        )

        self.recording = True
        self.audio_chunks = []

        self.thread = threading.Thread(
            target=self._record_loop,
            daemon=True,
        )

        self.thread.start()

        logger.info(
            "SLACK RECORDER STARTED | huddle_id=%s",
            self.huddle_id
        )

    # --------------------------------------------------------
    # RECORD LOOP
    # --------------------------------------------------------

    def _record_loop(self):
        """
        Continuously capture microphone and loopback audio.
        """

        chunk_frames = int(
            SAMPLE_RATE * CHUNK_SECONDS
        )

        try:

            with self.microphone.recorder(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
            ) as mic_recorder, self.loopback.recorder(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
            ) as loopback_recorder:

                while self.recording:

                    mic_audio = mic_recorder.record(
                        numframes=chunk_frames
                    )

                    system_audio = loopback_recorder.record(
                        numframes=chunk_frames
                    )

                    mic_audio = np.asarray(
                        mic_audio,
                        dtype=np.float32
                    )

                    system_audio = np.asarray(
                        system_audio,
                        dtype=np.float32
                    )

                    # ------------------------------------------------
                    # Make sure both sources have the same shape
                    # ------------------------------------------------

                    frames = min(
                        len(mic_audio),
                        len(system_audio)
                    )

                    mic_audio = mic_audio[:frames]
                    system_audio = system_audio[:frames]

                    # ------------------------------------------------
                    # Mix microphone + system audio
                    # ------------------------------------------------

                    combined = (
                        mic_audio * 0.5
                        + system_audio * 0.5
                    )

                    # Prevent clipping.
                    combined = np.clip(
                        combined,
                        -1.0,
                        1.0
                    )

                    self.audio_chunks.append(
                        combined
                    )

                    # ------------------------------------------------
                    # Diagnostics
                    # ------------------------------------------------

                    mic_rms = float(
                        np.sqrt(
                            np.mean(
                                mic_audio ** 2
                            )
                        )
                    )

                    system_rms = float(
                        np.sqrt(
                            np.mean(
                                system_audio ** 2
                            )
                        )
                    )

                    logger.debug(
                        "Audio levels | MIC=%.5f | SYSTEM=%.5f",
                        mic_rms,
                        system_rms,
                    )

        except Exception:
            logger.exception(
                "Recorder failed | huddle_id=%s",
                self.huddle_id
            )

            self.recording = False

    # --------------------------------------------------------
    # STOP
    # --------------------------------------------------------

    def stop(self):
        """
        Stop recording and save the WAV file.

        Returns:
            Path to the recorded WAV file.
        """

        if not self.recording:
            logger.warning(
                "Recorder is not running | huddle_id=%s",
                self.huddle_id
            )
            return self.output_path

        logger.info(
            "Stopping recorder | huddle_id=%s",
            self.huddle_id
        )

        self.recording = False

        if self.thread:
            self.thread.join(timeout=5)

        if not self.audio_chunks:
            logger.warning(
                "No audio captured | huddle_id=%s",
                self.huddle_id
            )
            return None

        audio = np.concatenate(
            self.audio_chunks,
            axis=0
        )

        # Convert float [-1, 1] to PCM16.
        pcm_audio = (
            audio * 32767
        ).astype(np.int16)

        with wave.open(
            self.output_path,
            "wb"
        ) as wav_file:

            wav_file.setnchannels(CHANNELS)
            wav_file.setsampwidth(2)
            wav_file.setframerate(SAMPLE_RATE)

            wav_file.writeframes(
                pcm_audio.tobytes()
            )

        duration = len(audio) / SAMPLE_RATE

        logger.info(
            "SLACK RECORDER STOPPED | huddle_id=%s | file=%s | duration=%.2fs",
            self.huddle_id,
            self.output_path,
            duration,
        )

        return self.output_path


# ============================================================
# PUBLIC API
# ============================================================

def start_recording(huddle_id: str):
    """
    Start a recording for a Slack Huddle.
    """

    huddle_id = str(huddle_id)

    if huddle_id in _active_recordings:
        logger.warning(
            "Recording already exists | huddle_id=%s",
            huddle_id
        )
        return

    recorder = SlackRecorder(huddle_id)

    recorder.start()

    _active_recordings[huddle_id] = recorder


def stop_recording(huddle_id: str):
    """
    Stop the recording for a Slack Huddle.

    Returns:
        WAV file path.
    """

    huddle_id = str(huddle_id)

    recorder = _active_recordings.pop(
        huddle_id,
        None
    )

    if recorder is None:
        logger.warning(
            "No active recorder found | huddle_id=%s",
            huddle_id
        )
        return None

    return recorder.stop()