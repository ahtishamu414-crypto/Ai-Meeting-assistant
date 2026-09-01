import time

from app.services.slack_recorder import (
    start_recording,
    stop_recording,
)


huddle_id = "test_huddle_001"

print("Starting recorder...")

start_recording(huddle_id)

print("Recording for 10 seconds...")
print("Speak into your microphone.")
print("Also play audio through your headphones.")

time.sleep(10)

print("Stopping recorder...")

path = stop_recording(huddle_id)

print(f"Recording saved to: {path}")