from sentence_transformers import SentenceTransformer

# Load the embedding model only once when the application starts
model = SentenceTransformer("all-MiniLM-L6-v2")


def create_embedding(text: str) -> list:
    """
    Generate embedding vector for any text.
    Returns a list of floating-point numbers.
    """

    if not text:
        return []

    embedding = model.encode(
        text,
        convert_to_numpy=True
    )

    return embedding.tolist()


def create_meeting_embedding(
    meeting_title: str,
    summary: str,
    topics: list,
    decisions: list
) -> list:
    """
    Create one embedding using all important meeting information.
    This produces much better search results than embedding only the summary.
    """

    combined_text = f"""
Meeting Title:
{meeting_title}

Summary:
{summary}

Topics:
{' '.join(topics)}

Decisions:
{' '.join(decisions)}
"""

    return create_embedding(combined_text)