# models.py
# Embedding + similarity utilities (CPU-only, local)
import numpy as np
from sentence_transformers import SentenceTransformer

# small, fast model that works on CPU
_EMB_MODEL_NAME = "all-MiniLM-L6-v2"
_embedder = None


def get_embedder():
    """
    Lazily load the sentence-transformers model once.
    """
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(_EMB_MODEL_NAME)
    return _embedder


def embed_texts(texts):
    """
    texts: list[str] -> np.ndarray (n, d)
    Normalized embeddings so we can use dot product as cosine.
    """
    emb = get_embedder()
    vecs = emb.encode(texts, normalize_embeddings=True)
    return np.array(vecs, dtype="float32")


def cosine_sim(a, b):
    """
    Cosine similarity for already-normalized vectors.
    a: (n, d)
    b: (m, d)
    returns: (n, m)
    """
    return a @ b.T
