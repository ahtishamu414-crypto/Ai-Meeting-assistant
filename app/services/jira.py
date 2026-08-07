import os
import requests
from dotenv import load_dotenv


load_dotenv()


JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")



def check_jira_config():
    """
    Check Jira environment variables.
    """

    missing = []

    if not JIRA_URL:
        missing.append("JIRA_URL")

    if not JIRA_EMAIL:
        missing.append("JIRA_EMAIL")

    if not JIRA_API_TOKEN:
        missing.append("JIRA_API_TOKEN")

    if not JIRA_PROJECT_KEY:
        missing.append("JIRA_PROJECT_KEY")


    if missing:
        raise Exception(
            f"Missing Jira configuration: {', '.join(missing)}"
        )



def create_jira_issue(action_text: str):
    """
    Create a single Jira issue.
    """

    if not action_text.strip():
        return None


    check_jira_config()


    # -----------------------------
    # Jira summary cannot contain
    # newline characters
    # -----------------------------

    summary_text = "AI Generated Task"


    for line in action_text.splitlines():

        line = line.strip()


        if not line:
            continue


        if line.startswith("Task:"):
            continue


        summary_text = line

        break



    url = f"{JIRA_URL}/rest/api/3/issue"


    headers = {

        "Accept": "application/json",

        "Content-Type": "application/json"

    }



    payload = {

        "fields": {


            "project": {

                "key": JIRA_PROJECT_KEY

            },


            "summary": summary_text[:255],


            "description": {

                "type": "doc",

                "version": 1,

                "content": [

                    {

                        "type": "paragraph",

                        "content": [

                            {

                                "type": "text",

                                "text":
                                    (
                                        "Created automatically by "
                                        "AI Meeting Assistant.\n\n"
                                        f"{action_text}"
                                    )

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



    try:

        response = requests.post(

            url,

            json=payload,

            headers=headers,

            auth=(

                JIRA_EMAIL,

                JIRA_API_TOKEN

            ),

            timeout=15

        )



        print(
            "Jira Status:",
            response.status_code
        )



        if response.status_code == 201:


            data = response.json()


            print(
                "✅ Jira issue created:",
                data.get("key")
            )


            return data



        else:

            print(
                "❌ Jira Error:"
            )

            print(
                response.text
            )


            return None



    except Exception as e:


        print(
            "❌ Jira Connection Error:",
            e
        )


        return None





def create_jira_issues(action_items):
    """
    Create Jira issues from AI extracted action items.

    Expected format:

    [
        {
            "task": "Prepare presentation",
            "owner": "Ali",
            "due_date": "Tomorrow"
        }
    ]

    """



    if not action_items:

        return



    # Backward compatibility
    # if old string format comes

    if isinstance(action_items, str):

        action_items = [

            {

                "task": action_items,

                "owner": "Not specified",

                "due_date": "Not specified"

            }

        ]



    for item in action_items:


        if not isinstance(item, dict):

            continue



        task = item.get(

            "task",

            ""

        )


        owner = item.get(

            "owner",

            "Not specified"

        )


        due_date = item.get(

            "due_date",

            "Not specified"

        )



        if not task.strip():

            continue



        jira_text = f"""
Task:
{task}

Owner:
{owner}

Due Date:
{due_date}
"""



        create_jira_issue(

            jira_text.strip()

        )