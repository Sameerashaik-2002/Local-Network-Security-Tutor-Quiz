# models.py
# Embedding + similarity utilities (CPU-only)
import numpy as np
from sentence_transformers import SentenceTransformer

_EMB_MODEL_NAME = "all-MiniLM-L6-v2"
_emb = None

def get_embedder():
    global _emb
    if _emb is None:
        _emb = SentenceTransformer(_EMB_MODEL_NAME)
    return _emb

def embed_texts(texts):
    emb = get_embedder()
    vecs = emb.encode(texts, normalize_embeddings=True)
    return np.array(vecs, dtype="float32")

def cosine_sim(a, b):
    # a: (n,d), b: (m,d)
    return a @ b.T
