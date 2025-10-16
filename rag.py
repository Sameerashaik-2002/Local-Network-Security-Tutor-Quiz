# rag.py
"""
Retrieval + answer composition + improved quiz generator/grader (CPU only).
"""
import os, random, re
from typing import List, Tuple, Dict, Any
import chromadb
from chromadb.config import Settings
import numpy as np
from models import embed_texts, cosine_sim

ROOT = os.path.dirname(__file__)
DB_DIR = os.path.join(ROOT, "data", "vectordb")
COLLECTION = "cs5342_kb"

# -------- Retrieval ----------
def _collection():
    client = chromadb.PersistentClient(path=DB_DIR, settings=Settings(allow_reset=False))
    return client.get_or_create_collection(COLLECTION, metadata={"hnsw:space":"cosine"})

def retrieve(query:str, k:int=4)->List[Tuple[str, Dict[str,str]]]:
    col = _collection()
    qv = embed_texts([query])[0].tolist()
    out = col.query(query_embeddings=[qv], n_results=k, include=["documents","metadatas"])
    docs = out.get("documents", [[]])[0]
    metas = out.get("metadatas", [[]])[0]
    return list(zip(docs, metas))

# -------- Q&A Tutor ----------
def make_answer(query:str, k:int=4)->Tuple[str, List[Dict[str, str]]]:
    hits = retrieve(query, k=k)
    if not hits:
        return ("I don't have any indexed materials yet. Add notes in data/seeds/ and run ingest.", [])
    ctx = " ".join([d for d,_ in hits])
    sentences = re.split(r'(?<=[.!?])\s+', ctx)
    svecs = embed_texts(sentences)
    qvec = embed_texts([query])
    sims = cosine_sim(svecs, qvec).ravel()
    top_idx = np.argsort(-sims)[:5]
    chosen = [sentences[i].strip() for i in top_idx if len(sentences[i].strip())>0]

    sources = []
    for _, m in hits:
        src = m.get("source", "local")
        if src not in sources:
            sources.append(src)
    cite_str = " ".join(f"[{i+1}: {s}]" for i, s in enumerate(sources, start=1))
    answer = " ".join(chosen) + f"\n\nSources: {cite_str}"
    return answer, [{"source": s} for s in sources]

# -------- Quiz Generator ----------
def generate_quiz(topic:str="", n:int=5)->Dict[str, Any]:
    q = topic if topic else "network security basics"
    hits = retrieve(q, k=max(6, n*2))
    if not hits:
        return {"topic": topic or "general", "items": []}

    base = " ".join([d for d,_ in hits])
    sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', base) if 40 < len(s) < 220]
    random.shuffle(sents)

    items = []
    for i, s in enumerate(sents[:n]):
        srcs = list({m.get("source","local") for _, m in hits[:3]})
        if i % 3 == 0:
            items.append({"type": "tf", "q": s, "answer": True, "sources": srcs})
        elif i % 3 == 1:
            words = s.split()
            if len(words) > 8:
                span = " ".join(words[2:5])
                stem = s.replace(span, "_____")
                opts = list({span, words[0], words[-1], "security"})
                while len(opts) < 4: opts.append("network")
                random.shuffle(opts)
                items.append({"type": "mcq", "q": stem, "options": opts, "answer": span, "sources": srcs})
            else:
                items.append({"type": "tf", "q": s, "answer": True, "sources": srcs})
        else:
            items.append({"type": "open", "q": f"Briefly explain: {s}", "answer": s, "sources": srcs})
    return {"topic": topic or "general", "items": items}

# -------- Quiz Grader ----------
def grade_quiz(items:List[Dict[str,Any]], responses:List[Any])->Dict[str, Any]:
    score = 0
    details = []
    for it, resp in zip(items, responses):
        correct = False
        rationale = ""
        if it["type"] == "tf":
            correct = bool(resp) == bool(it["answer"])
            rationale = "True/False comparison"
        elif it["type"] == "mcq":
            correct = str(resp).strip() == str(it["answer"]).strip()
            rationale = "Exact option match"
        else:
            ref = it.get("answer","")
            sim = float(cosine_sim(embed_texts([ref]), embed_texts([str(resp)])).ravel()[0])
            correct = sim >= 0.55
            rationale = f"Semantic similarity {sim:.2f}"
        score += 1 if correct else 0
        details.append({
            "question": it["q"],
            "your_answer": resp,
            "expected": it.get("answer",""),
            "correct": correct,
            "sources": it.get("sources",[]),
            "rationale": rationale
        })
    return {"score": score, "total": len(items), "details": details}
