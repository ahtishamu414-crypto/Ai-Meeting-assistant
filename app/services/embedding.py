from sentence_transformers import SentenceTransformer


# --------------------------------------------------
# Load embedding model once
# --------------------------------------------------

model = SentenceTransformer("all-MiniLM-L6-v2")


# --------------------------------------------------
# Create basic embedding
# --------------------------------------------------

def create_embedding(text: str) -> list:
    """
    Generate a 384-dimensional embedding vector.

    Returns:
        list: Floating-point embedding values.
    """

    if not text or not text.strip():
        return []

    embedding = model.encode(
        text,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    return embedding.tolist()


# --------------------------------------------------
# Create meeting embedding
# --------------------------------------------------

def create_meeting_embedding(
    meeting_title: str,
    summary: str,
    topics: list,
    decisions: list,
    open_questions: list,
    key_points: list,
    action_items: list
) -> list:
    """
    Create one semantic embedding containing
    the important information from a meeting.

    This embedding is later used for semantic search.
    """

    # ----------------------------------------------
    # Convert topics
    # ----------------------------------------------

    topics_text = " ".join(
        str(item)
        for item in topics
        if item
    )


    # ----------------------------------------------
    # Convert decisions
    # ----------------------------------------------

    decisions_text = " ".join(
        str(item)
        for item in decisions
        if item
    )


    # ----------------------------------------------
    # Convert open questions
    # ----------------------------------------------

    open_questions_text = " ".join(
        str(item)
        for item in open_questions
        if item
    )


    # ----------------------------------------------
    # Convert key points
    # ----------------------------------------------

    key_points_text = " ".join(
        str(item)
        for item in key_points
        if item
    )


    # ----------------------------------------------
    # Convert action items
    # ----------------------------------------------

    action_items_text = " ".join(

        (
            f"Task: {item.get('task', '')}. "
            f"Owner: {item.get('owner', '')}. "
            f"Due date: {item.get('due_date', '')}."
        )

        for item in action_items

        if isinstance(item, dict)
    )


    # ----------------------------------------------
    # Combine meeting information
    # ----------------------------------------------

    combined_text = f"""
Meeting Title:
{meeting_title}

Summary:
{summary}

Topics:
{topics_text}

Decisions:
{decisions_text}

Open Questions:
{open_questions_text}

Key Points:
{key_points_text}

Action Items:
{action_items_text}
""".strip()


    # ----------------------------------------------
    # Generate embedding
    # ----------------------------------------------

    return create_embedding(
        combined_text
    )