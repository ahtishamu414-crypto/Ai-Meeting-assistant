from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from app.database import meetings_collection


# ============================================================
# LOAD EMBEDDING MODEL ONCE
# ============================================================

model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2"
)


# ============================================================
# SEARCH MEETINGS
# ============================================================

def search_meetings(
    query: str,
    top_k: int = 3
):
    """
    Perform semantic search over stored meetings.

    Returns the most relevant meetings along with:
        - meeting_id
        - meeting title
        - similarity score
        - uploaded date
        - summary
        - decisions
        - action items
        - transcript
    """

    if not query or not query.strip():

        return []


    # ========================================================
    # 1. CREATE QUERY EMBEDDING
    # ========================================================

    query_embedding = model.encode(
        query,
        convert_to_numpy=True
    ).tolist()


    # ========================================================
    # 2. GET MEETINGS WITH VALID EMBEDDINGS
    # ========================================================

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


    # ========================================================
    # 3. CALCULATE SIMILARITY
    # ========================================================

    results = []


    for meeting in meetings:

        embedding = meeting.get(
            "embedding",
            []
        )


        # ----------------------------------------------------
        # Skip invalid embeddings
        # ----------------------------------------------------

        if not embedding:

            continue


        if len(embedding) != len(query_embedding):

            continue


        try:

            score = cosine_similarity(
                [query_embedding],
                [embedding]
            )[0][0]

        except Exception as e:

            print(
                "Similarity calculation error:",
                e
            )

            continue


        # ----------------------------------------------------
        # Ignore very weak matches
        # ----------------------------------------------------

        if score < 0.15:

            continue


        # ====================================================
        # BUILD SEARCH RESULT
        # ====================================================

        results.append(

            {
                # MongoDB ID
                "meeting_id":
                    str(meeting.get("_id")),

                # Similarity
                "similarity":
                    float(score),

                # Metadata
                "meeting_title":
                    meeting.get(
                        "meeting_title",
                        "Untitled Meeting"
                    ),

                "uploaded_at":
                    meeting.get(
                        "uploaded_at"
                    ),

                "filename":
                    meeting.get(
                        "filename",
                        ""
                    ),

                # Speaker information
                "speakers":
                    meeting.get(
                        "speakers",
                        []
                    ),

                "speaker_count":
                    meeting.get(
                        "speaker_count",
                        0
                    ),

                # Meeting analysis
                "summary":
                    meeting.get(
                        "summary",
                        ""
                    ),

                "topics":
                    meeting.get(
                        "topics",
                        []
                    ),

                "decisions":
                    meeting.get(
                        "decisions",
                        []
                    ),

                "open_questions":
                    meeting.get(
                        "open_questions",
                        []
                    ),

                "key_points":
                    meeting.get(
                        "key_points",
                        []
                    ),

                "action_items":
                    meeting.get(
                        "action_items",
                        []
                    ),

                # Full transcript
                "transcript":
                    meeting.get(
                        "transcript",
                        ""
                    )
            }
        )


    # ========================================================
    # 4. SORT BY SIMILARITY
    # ========================================================

    results.sort(
        key=lambda x: x["similarity"],
        reverse=True
    )


    # ========================================================
    # 5. REMOVE DUPLICATE MEETINGS
    # ========================================================

    unique_results = []

    seen_ids = set()


    for result in results:

        meeting_id = result["meeting_id"]


        if meeting_id in seen_ids:

            continue


        seen_ids.add(
            meeting_id
        )


        unique_results.append(
            result
        )


        if len(unique_results) >= top_k:

            break


    return unique_results