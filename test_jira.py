import os
import requests
from dotenv import load_dotenv

load_dotenv()

JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")

url = f"{JIRA_URL}/rest/api/3/issue"

headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}

payload = {
    "fields": {
        "project": {
            "key": JIRA_PROJECT_KEY
        },
        "summary": "Test Task from AI Meeting Assistant",
        "description": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "This task was created automatically using the Jira REST API."
                        }
                    ]
                }
            ]
        },
        "issuetype": {
            "name": "Task"
        }
    }
}

response = requests.post(
    url,
    json=payload,
    headers=headers,
    auth=(JIRA_EMAIL, JIRA_API_TOKEN),
)

print("Status Code:", response.status_code)
print("Response:")
print(response.text)