import re
import ollama

from app.services.search import search_meetings


# ============================================================
# CONFIGURATION
# ============================================================

OLLAMA_MODEL = "llama3.2:3b"

DEFAULT_TOP_K = 3

MAX_TRANSCRIPT_EVIDENCE = 8

MAX_SOURCE_EVIDENCE = 5


# ============================================================
# STOP WORDS
# ============================================================

STOP_WORDS = {
    "what",
    "when",
    "where",
    "who",
    "why",
    "how",
    "did",
    "does",
    "do",
    "is",
    "was",
    "were",
    "are",
    "the",
    "a",
    "an",
    "to",
    "of",
    "for",
    "in",
    "on",
    "and",
    "or",
    "we",
    "they",
    "our",
    "their",
    "about",
    "with",
    "from",
    "this",
    "that",
    "it",
    "be",
    "been",
    "has",
    "have",
    "had",
    "will",
    "would",
    "could",
    "should",
    "can",
    "did",
    "you",
    "your",
    "me",
    "us",
}


# ============================================================
# QUESTION TYPE DETECTION
# ============================================================

def detect_question_type(question: str):
    """
    Detect what kind of information the user is asking for.

    This helps us prioritize the correct meeting fields.
    """

    question_lower = question.lower()

    # --------------------------------------------------------
    # Decision questions
    # --------------------------------------------------------

    decision_patterns = [
        r"\bwhat did we decide\b",
        r"\bwhat was decided\b",
        r"\bwhat decision\b",
        r"\bwhat decisions\b",
        r"\bdecision about\b",
        r"\bdecided about\b",
        r"\bdecide about\b",
        r"\bwhat did .* decide\b",
        r"\bwhat have we decided\b",
        r"\bwhat was the final decision\b",
    ]

    for pattern in decision_patterns:

        if re.search(
            pattern,
            question_lower
        ):
            return "decision"

    # --------------------------------------------------------
    # Action-item questions
    # --------------------------------------------------------

    action_patterns = [
        r"\bwhat needs to be done\b",
        r"\bwhat needs doing\b",
        r"\bwhat are the action items\b",
        r"\bwhat is the action item\b",
        r"\bwho will\b",
        r"\bwho is responsible\b",
        r"\bwho needs to\b",
        r"\bwhat should .* do\b",
        r"\bwhat will .* do\b",
    ]

    for pattern in action_patterns:

        if re.search(
            pattern,
            question_lower
        ):
            return "action"

    # --------------------------------------------------------
    # Summary questions
    # --------------------------------------------------------

    summary_patterns = [
        r"\bsummarize\b",
        r"\bsummary\b",
        r"\bwhat was discussed\b",
        r"\bwhat did we discuss\b",
        r"\bwhat was the meeting about\b",
        r"\bwhat did .* talk about\b",
    ]

    for pattern in summary_patterns:

        if re.search(
            pattern,
            question_lower
        ):
            return "summary"

    # --------------------------------------------------------
    # Topic questions
    # --------------------------------------------------------

    topic_patterns = [
        r"\bwhat topics\b",
        r"\bwhich topics\b",
        r"\bwhat were the topics\b",
    ]

    for pattern in topic_patterns:

        if re.search(
            pattern,
            question_lower
        ):
            return "topic"

    # --------------------------------------------------------
    # Default
    # --------------------------------------------------------

    return "general"


# ============================================================
# EXTRACT QUESTION KEYWORDS
# ============================================================

def extract_question_keywords(
    question: str
):
    """
    Extract meaningful words from the question.
    """

    words = re.findall(
        r"\b[a-zA-Z0-9$]+\b",
        question.lower()
    )

    keywords = []

    for word in words:

        if word in STOP_WORDS:
            continue

        if len(word) <= 1:
            continue

        keywords.append(
            word
        )

    return set(
        keywords
    )


# ============================================================
# NORMALIZE TEXT
# ============================================================

def normalize_text(
    text
):
    """
    Normalize text for comparison.
    """

    if text is None:
        return ""

    if not isinstance(
        text,
        str
    ):
        text = str(text)

    text = text.lower()

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# CHECK KEYWORD MATCH
# ============================================================

def keyword_match_score(
    text: str,
    question_keywords
):
    """
    Calculate how many question keywords appear
    in the provided text.
    """

    if not text:
        return 0

    normalized = normalize_text(
        text
    )

    score = 0

    for word in question_keywords:

        pattern = rf"\b{re.escape(word)}\b"

        if re.search(
            pattern,
            normalized
        ):
            score += 1

    return score


# ============================================================
# EXTRACT TRANSCRIPT BLOCKS
# ============================================================

def split_transcript(
    transcript: str
):
    """
    Split transcript into blocks.

    Expected format:

    [00:00 - 00:08] SPEAKER_00
    Speaker text...

    [00:08 - 00:16] SPEAKER_00
    Speaker text...
    """

    if not transcript:
        return []

    blocks = re.split(
        r"\n\s*\n",
        transcript
    )

    cleaned_blocks = []

    for block in blocks:

        block = block.strip()

        if block:
            cleaned_blocks.append(
                block
            )

    return cleaned_blocks


# ============================================================
# EXTRACT RELEVANT TRANSCRIPT EVIDENCE
# ============================================================

def extract_relevant_evidence(
    transcript: str,
    question: str,
    max_evidence: int = MAX_TRANSCRIPT_EVIDENCE
):
    """
    Extract relevant transcript blocks.

    This uses keyword matching as a lightweight retrieval
    layer.

    Important:
    We additionally detect decision/action questions so
    the system does not rely only on exact words like
    "decide".
    """

    if not transcript:
        return []

    question_keywords = extract_question_keywords(
        question
    )

    blocks = split_transcript(
        transcript
    )

    if not blocks:
        return []

    question_type = detect_question_type(
        question
    )

    scored_blocks = []

    for block in blocks:

        block_lower = normalize_text(
            block
        )

        score = keyword_match_score(
            block_lower,
            question_keywords
        )

        # ----------------------------------------------------
        # Decision question boost
        # ----------------------------------------------------

        if question_type == "decision":

            decision_words = {
                "decide",
                "decision",
                "offer",
                "propose",
                "proposal",
                "agree",
                "agreed",
                "choose",
                "selected",
                "final",
                "should",
                "price",
                "pricing",
            }

            for word in decision_words:

                pattern = rf"\b{re.escape(word)}\b"

                if re.search(
                    pattern,
                    block_lower
                ):
                    score += 2

        # ----------------------------------------------------
        # Action question boost
        # ----------------------------------------------------

        if question_type == "action":

            action_words = {
                "prepare",
                "send",
                "create",
                "review",
                "update",
                "complete",
                "assigned",
                "responsible",
                "will",
            }

            for word in action_words:

                pattern = rf"\b{re.escape(word)}\b"

                if re.search(
                    pattern,
                    block_lower
                ):
                    score += 2

        # ----------------------------------------------------
        # Summary question
        # ----------------------------------------------------

        if question_type == "summary":

            summary_words = {
                "discuss",
                "discussed",
                "meeting",
                "talk",
                "talked",
                "topic",
            }

            for word in summary_words:

                pattern = rf"\b{re.escape(word)}\b"

                if re.search(
                    pattern,
                    block_lower
                ):
                    score += 1

        if score > 0:

            scored_blocks.append(
                (
                    score,
                    block
                )
            )

    # --------------------------------------------------------
    # Highest relevance first
    # --------------------------------------------------------

    scored_blocks.sort(
        key=lambda item: item[0],
        reverse=True
    )

    evidence = []

    for score, block in scored_blocks:

        if block not in evidence:

            evidence.append(
                block
            )

        if len(evidence) >= max_evidence:
            break

    return evidence


# ============================================================
# FORMAT LIST
# ============================================================

def format_list(
    values
):
    """
    Convert lists into readable text.
    """

    if not values:
        return "None"

    lines = []

    for value in values:

        if isinstance(
            value,
            dict
        ):

            lines.append(
                f"- {value}"
            )

        else:

            lines.append(
                f"- {value}"
            )

    return "\n".join(
        lines
    )


# ============================================================
# FORMAT ACTION ITEMS
# ============================================================

def format_action_items(
    action_items
):
    """
    Format action items in a readable way.
    """

    if not action_items:
        return "None"

    lines = []

    for item in action_items:

        if not isinstance(
            item,
            dict
        ):

            lines.append(
                f"- {item}"
            )

            continue

        task = item.get(
            "task",
            "Not specified"
        )

        owner = item.get(
            "owner",
            "Not specified"
        )

        due_date = item.get(
            "due_date",
            "Not specified"
        )

        status = item.get(
            "status",
            "pending"
        )

        lines.append(
            f"- Task: {task} | "
            f"Owner: {owner} | "
            f"Due: {due_date} | "
            f"Status: {status}"
        )

    return "\n".join(
        lines
    )


# ============================================================
# EXTRACT STRUCTURED EVIDENCE
# ============================================================

def extract_structured_evidence(
    meeting,
    question
):
    """
    Extract structured meeting information that is
    particularly relevant to the question.

    Decisions are prioritized for decision questions.
    Action items are prioritized for responsibility questions.
    """

    question_type = detect_question_type(
        question
    )

    evidence = []

    # --------------------------------------------------------
    # Decisions
    # --------------------------------------------------------

    decisions = meeting.get(
        "decisions",
        []
    )

    if decisions:

        for decision in decisions:

            evidence.append(
                f"DECISION: {decision}"
            )

    # --------------------------------------------------------
    # Action Items
    # --------------------------------------------------------

    action_items = meeting.get(
        "action_items",
        []
    )

    if action_items:

        for item in action_items:

            if isinstance(
                item,
                dict
            ):

                task = item.get(
                    "task",
                    "Not specified"
                )

                owner = item.get(
                    "owner",
                    "Not specified"
                )

                due_date = item.get(
                    "due_date",
                    "Not specified"
                )

                status = item.get(
                    "status",
                    "pending"
                )

                evidence.append(
                    "ACTION ITEM: "
                    f"{task} | "
                    f"Owner: {owner} | "
                    f"Due: {due_date} | "
                    f"Status: {status}"
                )

            else:

                evidence.append(
                    f"ACTION ITEM: {item}"
                )

    # --------------------------------------------------------
    # Key Points
    # --------------------------------------------------------

    key_points = meeting.get(
        "key_points",
        []
    )

    for point in key_points:

        evidence.append(
            f"KEY POINT: {point}"
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    summary = meeting.get(
        "summary",
        ""
    )

    if summary:

        evidence.append(
            f"SUMMARY: {summary}"
        )

    # --------------------------------------------------------
    # Topics
    # --------------------------------------------------------

    topics = meeting.get(
        "topics",
        []
    )

    for topic in topics:

        evidence.append(
            f"TOPIC: {topic}"
        )

    # --------------------------------------------------------
    # Reorder based on question type
    # --------------------------------------------------------

    if question_type == "decision":

        decisions_evidence = [
            item
            for item in evidence
            if item.startswith(
                "DECISION:"
            )
        ]

        other_evidence = [
            item
            for item in evidence
            if not item.startswith(
                "DECISION:"
            )
        ]

        evidence = (
            decisions_evidence
            + other_evidence
        )

    elif question_type == "action":

        action_evidence = [
            item
            for item in evidence
            if item.startswith(
                "ACTION ITEM:"
            )
        ]

        other_evidence = [
            item
            for item in evidence
            if not item.startswith(
                "ACTION ITEM:"
            )
        ]

        evidence = (
            action_evidence
            + other_evidence
        )

    return evidence


# ============================================================
# BUILD MEETING CONTEXT
# ============================================================

def build_meeting_context(
    results,
    question
):
    """
    Build the complete RAG context.

    Important design:

        Structured information
                 +
        Transcript evidence
                 +
        Full transcript

    This prevents the LLM from missing an already extracted
    decision or action item.
    """

    context_parts = []

    for index, meeting in enumerate(
        results,
        start=1
    ):

        meeting_id = meeting.get(
            "meeting_id",
            ""
        )

        meeting_title = meeting.get(
            "meeting_title",
            "Untitled Meeting"
        )

        similarity = meeting.get(
            "similarity",
            0
        )

        uploaded_at = meeting.get(
            "uploaded_at",
            ""
        )

        speakers = meeting.get(
            "speakers",
            []
        )

        speaker_count = meeting.get(
            "speaker_count",
            0
        )

        summary = meeting.get(
            "summary",
            ""
        )

        topics = meeting.get(
            "topics",
            []
        )

        decisions = meeting.get(
            "decisions",
            []
        )

        open_questions = meeting.get(
            "open_questions",
            []
        )

        key_points = meeting.get(
            "key_points",
            []
        )

        action_items = meeting.get(
            "action_items",
            []
        )

        transcript = meeting.get(
            "transcript",
            ""
        )

        # ----------------------------------------------------
        # Transcript evidence
        # ----------------------------------------------------

        transcript_evidence = extract_relevant_evidence(
            transcript,
            question,
            max_evidence=MAX_TRANSCRIPT_EVIDENCE
        )

        transcript_evidence_text = "\n\n".join(
            transcript_evidence
        )

        if not transcript_evidence_text:
            transcript_evidence_text = "None"

        # ----------------------------------------------------
        # Structured evidence
        # ----------------------------------------------------

        structured_evidence = extract_structured_evidence(
            meeting,
            question
        )

        structured_evidence_text = "\n".join(
            structured_evidence
        )

        if not structured_evidence_text:
            structured_evidence_text = "None"

        # ----------------------------------------------------
        # Build meeting context
        # ----------------------------------------------------

        context_parts.append(
            f"""
============================================================
MEETING {index}
============================================================

MEETING ID:
{meeting_id}

MEETING TITLE:
{meeting_title}

SIMILARITY:
{similarity:.4f}

UPLOADED AT:
{uploaded_at}

SPEAKERS:
{speakers}

SPEAKER COUNT:
{speaker_count}


------------------------------------------------------------
SUMMARY
------------------------------------------------------------

{summary}


------------------------------------------------------------
TOPICS
------------------------------------------------------------

{format_list(topics)}


------------------------------------------------------------
DECISIONS
------------------------------------------------------------

{format_list(decisions)}


------------------------------------------------------------
OPEN QUESTIONS
------------------------------------------------------------

{format_list(open_questions)}


------------------------------------------------------------
KEY POINTS
------------------------------------------------------------

{format_list(key_points)}


------------------------------------------------------------
ACTION ITEMS
------------------------------------------------------------

{format_action_items(action_items)}


------------------------------------------------------------
STRUCTURED EVIDENCE
------------------------------------------------------------

{structured_evidence_text}


------------------------------------------------------------
RELEVANT TRANSCRIPT EVIDENCE
------------------------------------------------------------

{transcript_evidence_text}


------------------------------------------------------------
FULL TRANSCRIPT
------------------------------------------------------------

{transcript}

============================================================
END OF MEETING {index}
============================================================
"""
        )

    return "\n".join(
        context_parts
    )


# ============================================================
# BUILD RAG PROMPT
# ============================================================

def build_rag_prompt(
    context,
    question
):
    """
    Build a strict RAG prompt.
    """

    return f"""
You are an AI Meeting Assistant.

You answer questions ONLY from the meeting information
provided below.

IMPORTANT:

The meeting data contains structured information extracted
from the meeting, including:

- SUMMARY
- TOPICS
- DECISIONS
- KEY POINTS
- ACTION ITEMS
- TRANSCRIPT EVIDENCE
- FULL TRANSCRIPT

Treat explicit DECISIONS and ACTION ITEMS as valid meeting
facts.

Do NOT ignore a decision just because the exact word
"decision" does not appear in the transcript.

For example, if the context says:

DECISION:
Offer $12,000 as the initial proposal

and the user asks:

"What did we decide about Client X pricing?"

the answer MUST use that decision.

============================================================
STRICT RULES
============================================================

1. Use ONLY the provided meeting context.

2. Do NOT use outside knowledge.

3. Do NOT guess.

4. Do NOT invent information.

5. Do NOT change names, prices, dates, decisions,
   responsibilities, or action items.

6. If a DECISION is explicitly provided, trust it.

7. If an ACTION ITEM is explicitly provided, trust it.

8. Use transcript evidence to support the answer.

9. If multiple meetings contain the same information,
   answer once instead of repeating it.

10. If the information cannot be found anywhere in the
    provided context, respond exactly:

I could not find this information.

11. Keep the answer concise.

12. Answer the question directly.

13. Do not mention the RAG system.

14. Do not mention the prompt.

15. Do not mention that you are an AI.

============================================================
MEETING CONTEXT
============================================================

{context}

============================================================
USER QUESTION
============================================================

{question}

============================================================
ANSWER
============================================================
"""


# ============================================================
# GENERATE ANSWER
# ============================================================

def generate_answer(
    prompt
):
    """
    Send prompt to Ollama.
    """

    try:

        response = ollama.chat(

            model=OLLAMA_MODEL,

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

        answer = response[
            "message"
        ][
            "content"
        ].strip()

        return answer

    except Exception as e:

        print(
            "❌ Ollama Error:",
            e
        )

        return None


# ============================================================
# BUILD SOURCES
# ============================================================

def build_sources(
    results,
    question
):
    """
    Build source information for the API response.
    """

    sources = []

    for meeting in results:

        transcript = meeting.get(
            "transcript",
            ""
        )

        evidence = extract_relevant_evidence(
            transcript,
            question,
            max_evidence=MAX_SOURCE_EVIDENCE
        )

        # ----------------------------------------------------
        # If transcript matching misses the answer,
        # include decisions/action items as evidence.
        # ----------------------------------------------------

        structured = extract_structured_evidence(
            meeting,
            question
        )

        # Prefer structured evidence for decision/action
        # questions.

        question_type = detect_question_type(
            question
        )

        if question_type == "decision":

            decision_evidence = [
                item
                for item in structured
                if item.startswith(
                    "DECISION:"
                )
            ]

            if decision_evidence:

                evidence = (
                    decision_evidence
                    + evidence
                )

        elif question_type == "action":

            action_evidence = [
                item
                for item in structured
                if item.startswith(
                    "ACTION ITEM:"
                )
            ]

            if action_evidence:

                evidence = (
                    action_evidence
                    + evidence
                )

        # ----------------------------------------------------
        # Remove duplicates
        # ----------------------------------------------------

        unique_evidence = []

        for item in evidence:

            if item not in unique_evidence:

                unique_evidence.append(
                    item
                )

        unique_evidence = unique_evidence[
            :MAX_SOURCE_EVIDENCE
        ]

        similarity = meeting.get(
            "similarity",
            0
        )

        try:

            similarity = round(
                float(similarity),
                4
            )

        except Exception:

            similarity = 0

        source = {

            "meeting_id":
                meeting.get(
                    "meeting_id"
                ),

            "meeting_title":
                meeting.get(
                    "meeting_title",
                    "Untitled Meeting"
                ),

            "similarity":
                similarity,

            "uploaded_at":
                meeting.get(
                    "uploaded_at"
                ),

            "evidence":
                unique_evidence
        }

        sources.append(
            source
        )

    return sources


# ============================================================
# ASK MEETING
# ============================================================

def ask_meeting(
    question: str,
    top_k: int = DEFAULT_TOP_K
):
    """
    Main RAG question-answering function.

    Pipeline:

        Question
           ↓
        Semantic Search
           ↓
        Relevant Meetings
           ↓
        Structured Evidence
           ↓
        Transcript Evidence
           ↓
        RAG Context
           ↓
        Ollama
           ↓
        Answer + Sources
    """

    # ========================================================
    # 1. VALIDATE QUESTION
    # ========================================================

    if not question:

        return {
            "question": question,
            "answer": "Please provide a question.",
            "sources": []
        }

    question = question.strip()

    if not question:

        return {
            "question": question,
            "answer": "Please provide a question.",
            "sources": []
        }

    # ========================================================
    # 2. VALIDATE TOP K
    # ========================================================

    try:

        top_k = int(
            top_k
        )

    except Exception:

        top_k = DEFAULT_TOP_K

    if top_k <= 0:

        top_k = DEFAULT_TOP_K

    # Prevent unnecessarily huge contexts.

    if top_k > 10:

        top_k = 10

    # ========================================================
    # 3. SEMANTIC SEARCH
    # ========================================================

    try:

        results = search_meetings(
            question,
            top_k=top_k
        )

    except Exception as e:

        print(
            "❌ Semantic Search Error:",
            e
        )

        return {
            "question": question,
            "answer": "Unable to search meeting information.",
            "sources": []
        }

    # ========================================================
    # 4. NO SEARCH RESULTS
    # ========================================================

    if not results:

        return {
            "question": question,
            "answer": "I could not find this information.",
            "sources": []
        }

    # ========================================================
    # 5. BUILD CONTEXT
    # ========================================================

    context = build_meeting_context(
        results,
        question
    )

    # ========================================================
    # 6. BUILD PROMPT
    # ========================================================

    prompt = build_rag_prompt(
        context,
        question
    )

    # ========================================================
    # 7. GENERATE ANSWER
    # ========================================================

    answer = generate_answer(
        prompt
    )

    # ========================================================
    # 8. HANDLE OLLAMA FAILURE
    # ========================================================

    if answer is None:

        return {
            "question": question,
            "answer": "Unable to generate an answer.",
            "sources": []
        }

    # ========================================================
    # 9. BUILD SOURCES
    # ========================================================

    sources = build_sources(
        results,
        question
    )

    # ========================================================
    # 10. FINAL RESPONSE
    # ========================================================

    return {

        "question":
            question,

        "answer":
            answer,

        "sources":
            sources
    }