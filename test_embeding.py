from app.services.embedding import create_embedding

embedding = create_embedding(
    "Ali will update the documentation before Thursday."
)

print("Embedding Length:", len(embedding))
print("First 10 values:")
print(embedding[:10])