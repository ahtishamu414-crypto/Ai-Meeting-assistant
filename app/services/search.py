from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from app.database import meetings_collection


# Load embedding model once
model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2"
)


def search_meetings(
    query: str,
    top_k: int = 3
):
    """
    Perform semantic search over stored meetings
    using cosine similarity.
    """

    # Create query embedding
    query_embedding = model.encode(
        query,
        convert_to_numpy=True
    ).tolist()

    # Get meetings with valid embeddings
    meetings = list(
        meetings_collection.find(
            {
                "embedding": {
                    "$exists": True,
                    "$ne": []
                }
            }
        )
    )

    if not meetings:
        return []

    results = []

    for meeting in meetings:

        embedding = meeting.get("embedding", [])

        # Skip invalid embeddings
        if not embedding:
            continue

        if len(embedding) != len(query_embedding):
            continue

        score = cosine_similarity(
            [query_embedding],
            [embedding]
        )[0][0]

        # Ignore weak semantic matches
        if score < 0.15:
            continue

        results.append(
            {
                "similarity": float(score),
                "meeting_title": meeting.get(
                    "meeting_title", ""
                ),
                "summary": meeting.get(
                    "summary", ""
                ),
                "topics": meeting.get(
                    "topics", []
                ),
                "decisions": meeting.get(
                    "decisions", []
                ),
                "open_questions": meeting.get(
                    "open_questions", []
                ),
                "key_points": meeting.get(
                    "key_points", []
                ),
                "action_items": meeting.get(
                    "action_items", []
                ),
                "transcript": meeting.get(
                    "transcript", ""
                )
            }
        )

    # Sort by similarity
    results.sort(
        key=lambda x: x["similarity"],
        reverse=True
    )

    # Remove duplicate meeting titles
    unique_results = []
    seen_titles = set()

    for result in results:

        title = result["meeting_title"]

        if title in seen_titles:
            continue

        seen_titles.add(title)
        unique_results.append(result)

        if len(unique_results) >= top_k:
            break

    return unique_results