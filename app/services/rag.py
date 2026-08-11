import ollama

from app.services.search import search_meetings


def ask_meeting(question: str):

    # -----------------------------------
    # Semantic Search
    # -----------------------------------

    results = search_meetings(
        question,
        top_k=3
    )

    if not results:
        return {
            "question": question,
            "answer": "I could not find this information.",
            "sources": []
        }

    # -----------------------------------
    # Build RAG Context
    # -----------------------------------

    context_parts = []

    for i, meeting in enumerate(results, start=1):

        context_parts.append(
            f"""
MEETING {i}

Meeting Title:
{meeting.get("meeting_title", "")}

Summary:
{meeting.get("summary", "")}

Topics:
{meeting.get("topics", [])}

Decisions:
{meeting.get("decisions", [])}

Open Questions:
{meeting.get("open_questions", [])}

Key Points:
{meeting.get("key_points", [])}

Action Items:
{meeting.get("action_items", [])}

Transcript:
{meeting.get("transcript", "")}
"""
        )

    context = "\n".join(context_parts)

    # -----------------------------------
    # RAG Prompt
    # -----------------------------------

    prompt = f"""
You are an AI Meeting Assistant.

Your job is to answer the user's question using ONLY the meeting
information provided below.

IMPORTANT RULES:

1. Do NOT use outside knowledge.
2. Do NOT guess.
3. Do NOT invent information.
4. If the answer is explicitly present in the context, answer directly.
5. If the answer is not present, respond exactly:
   I could not find this information.
6. Prefer specific action items, decisions, and transcript information
   over general assumptions.
7. Keep the answer short and direct.
8. Do not mention that this is a TV show, movie, conversation,
   or anything unrelated to the meeting.

MEETING CONTEXT:
{context}

USER QUESTION:
{question}

ANSWER:
"""

    # -----------------------------------
    # Ollama
    # -----------------------------------

    response = ollama.chat(
        model="llama3.2:3b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        options={
            "temperature": 0
        }
    )

    answer = response["message"]["content"].strip()

    # -----------------------------------
    # Sources
    # -----------------------------------

    sources = []

    for meeting in results:

        title = meeting.get(
            "meeting_title",
            "Untitled Meeting"
        )

        if title not in sources:
            sources.append(title)

    # -----------------------------------
    # Response
    # -----------------------------------

    return {
        "question": question,
        "answer": answer,
        "sources": sources
    }