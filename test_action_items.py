from app.services.action_items import extract_action_items

text = """
Ali will finish the backend by Friday.

Sara will prepare the presentation.

Ahmed should deploy the application tomorrow.
"""

print(extract_action_items(text))