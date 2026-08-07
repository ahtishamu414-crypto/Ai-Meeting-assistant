import os
import requests
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SLACK_WEBHOOK_URL")

print("Webhook Loaded:", bool(url))

response = requests.post(
    url,
    json={"text": "✅ Hello from AI Meeting Assistant"},
)

print("Status Code:", response.status_code)
print("Response:", response.text)