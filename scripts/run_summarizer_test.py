import sys
from pathlib import Path

# Ensure project root is on sys.path so `app` package can be imported
project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.services.summarizer import summarize_text

if __name__ == '__main__':
    try:
        print('Calling summarize_text with a longer sample...')
        long_text = (
            "Attendees discussed project timeline, budget overruns, and resource allocation. "
            "We agreed to push the release by two weeks, assign two more engineers to the backend, "
            "and schedule weekly check-ins. Action items: Alice to update the roadmap, Bob to adjust the budget, "
            "Carol to onboard the new hires. Next meeting in one week."
        )
        res = summarize_text(long_text)
        print('Result:\n', res)
    except Exception as e:
        import traceback
        traceback.print_exc()
