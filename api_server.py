# api_server.py
import os
import re
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Local NetSec Helper API")

# where your markdown/txt notes live
DATA_DIR = os.path.join("data", "seeds")


def load_notes() -> str:
    """Load all .md/.txt under data/seeds/ into one big string."""
    texts = []
    for root, _, files in os.walk(DATA_DIR):
        for f in files:
            if f.endswith(".md") or f.endswith(".txt"):
                path = os.path.join(root, f)
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        texts.append(fh.read())
                except Exception:
                    pass
    return "\n".join(texts)


NOTES_TEXT = load_notes()


def split_sentences(text: str):
    # basic sentence splitter
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def search_local(term: str) -> str:
    """
    1. try exact phrase
    2. if not found, try each word
    3. prefer security keywords like 'integrity'
    """
    if not NOTES_TEXT.strip():
        return "No local notes loaded yet."

    term_norm = term.lower().strip()
    sentences = split_sentences(NOTES_TEXT)

    # 1) exact phrase
    exact_hits = [s for s in sentences if term_norm in s.lower()]
    if exact_hits:
        return " ".join(exact_hits[:3])

    # 2) word-level match
    words = [w for w in re.split(r"\s+", term_norm) if w]
    word_hits = []
    for s in sentences:
        s_low = s.lower()
        if any(w in s_low for w in words):
            word_hits.append(s)
    if word_hits:
        return " ".join(word_hits[:3])

    # 3) special case: integrity/availability/confidentiality
    cia_words = ["integrity", "availability", "confidentiality"]
    if any(w in term_norm for w in cia_words):
        cia_hits = [s for s in sentences if any(c in s.lower() for c in cia_words)]
        if cia_hits:
            return " ".join(cia_hits[:3])

    return f"No mention related to '{term}' found in local notes."


# ------------------ API ROUTES ------------------

class ExplainRequest(BaseModel):
    term: str


@app.get("/")
def root():
    return {"status": "ok", "msg": "Local NetSec API running"}


@app.post("/explain")
def explain(req: ExplainRequest):
    term = req.term
    explanation = search_local(term)
    return {
        "term": term,
        "explanation": explanation,
        "source": "local-notes"
    }
