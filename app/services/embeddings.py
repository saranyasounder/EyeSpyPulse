from sentence_transformers import SentenceTransformer

# Loaded once per process — model loading is the expensive part.
# 'all-MiniLM-L6-v2' is a good default: fast, small, strong general-purpose
# semantic quality. Good enough to discover topic structure; you can upgrade
# to a larger model later if cluster quality needs improvement.
_model = SentenceTransformer("all-MiniLM-L6-v2")


def get_embedding(text: str) -> list[float]:
    """Convert a single piece of text into a semantic embedding vector."""
    return _model.encode(text, normalize_embeddings=True).tolist()


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Batch version — much faster than calling get_embedding in a loop."""
    return _model.encode(texts, normalize_embeddings=True).tolist()