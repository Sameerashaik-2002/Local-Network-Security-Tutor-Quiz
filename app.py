import os
import csv
from datetime import datetime
import subprocess

import streamlit as st
import requests  # for calling the local FastAPI
from rag import make_answer, generate_quiz, grade_quiz

# ---------- local audit log ----------
LOG_DIR = os.path.join("data", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, "app_events.csv")


def log_event(event_type: str, details: str):
    """Append user actions to a local CSV for auditing/privacy evidence."""
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([datetime.now().isoformat(timespec="seconds"), event_type, details])


# ---------- page config ----------
st.set_page_config(page_title="CS5342 Local Tutor", page_icon="🛡️", layout="wide")
st.title("🛡️ CS5342 Local Network-Security Tutor & Quiz (Offline)")


# ---------- sidebar ----------
with st.sidebar:
    st.header("📂 Index Builder")
    st.write("Add your notes in `data/` (Markdown/PDF/TXT). Then rebuild.")
    if st.button("🔄 Build / Rebuild Index"):
        with st.spinner("Indexing your materials..."):
            result = subprocess.run(["python", "ingest.py"], capture_output=True, text=True)
            st.code(result.stdout + "\n" + result.stderr)
        log_event("ingest", "rebuild index from data/")
    st.divider()
    st.caption("All processing stays on your machine.")


# ---------- tabs ----------
tab1, tab2, tab3 = st.tabs(["💬 Tutor Agent", "📝 Quiz Agent", "🔐 Security & API"])


# ================= TUTOR AGENT =================
with tab1:
    st.subheader("Ask a Question (Tutor Agent)")
    query = st.text_input(
        "Enter your network-security question:",
        placeholder="e.g., What is the purpose of a firewall?",
    )
    k = st.slider("Number of reference sources to consider", 2, 8, 4)

    if st.button("Get Answer", type="primary"):
        if not query.strip():
            st.warning("Please enter a question first.")
        else:
            with st.spinner("Searching your local knowledge base..."):
                answer, sources = make_answer(query, k=k)
            st.markdown("### 🧠 Answer")
            st.write(answer)
            log_event("tutor_query", query)
            if sources:
                with st.expander("📎 Sources used"):
                    for i, s in enumerate(sources, start=1):
                        st.write(f"[{i}] {s['source']}")


# ================= QUIZ AGENT =================
with tab2:
    st.subheader("Generate and Take a Quiz")
    c1, c2 = st.columns(2)
    with c1:
        topic = st.text_input(
            "Topic (optional):", placeholder="e.g., TLS, firewalls, IDS, VPN"
        )
    with c2:
        n = st.slider("Number of questions", 3, 10, 5)

    if st.button("🎲 Generate Quiz"):
        with st.spinner("Generating quiz questions..."):
            st.session_state.quiz = generate_quiz(topic, n)
        st.success("Quiz generated successfully!")
        log_event("quiz_generate", f"topic={topic or 'general'};n={n}")

    if "quiz" in st.session_state:
        quiz = st.session_state.quiz
        if not quiz["items"]:
            st.warning("No quiz questions available. Try rebuilding your index.")
        else:
            st.markdown(
                f"**Topic:** {quiz['topic'].title()}  | **Total Questions:** {len(quiz['items'])}"
            )
            st.divider()

            answers = []
            all_answered = True

            for i, item in enumerate(quiz["items"], start=1):
                st.markdown(f"**Q{i}.** {item['q']}")

                if item["type"] == "tf":
                    resp = st.radio(
                        f"Answer {i}",
                        options=[True, False],
                        key=f"tf_{i}",
                        index=None,
                    )
                elif item["type"] == "mcq":
                    resp = st.radio(
                        f"Select option {i}",
                        options=item["options"],
                        key=f"mcq_{i}",
                        index=None,
                    )
                else:  # open-ended
                    text = st.text_area(
                        f"Your response {i}", key=f"open_{i}", height=80
                    )
                    resp = text.strip() if text.strip() else None

                if resp is None:
                    all_answered = False
                answers.append(resp)
                st.divider()

            if st.button("✅ Grade Quiz", disabled=not all_answered):
                with st.spinner("Evaluating your responses..."):
                    result = grade_quiz(quiz["items"], answers)
                st.success(f"**Your Score:** {result['score']} / {result['total']}")
                log_event("quiz_grade", f"score={result['score']}/{result['total']}")
                for d in result["details"]:
                    icon = "✅" if d["correct"] else "❌"
                    st.markdown(f"{icon} **Question:** {d['question']}")
                    st.write(f"- **Your Answer:** {d['your_answer']}")
                    st.write(f"- **Expected:** {d['expected']}")
                    st.write(f"- **Reasoning:** {d['rationale']}")
                    if d.get("sources"):
                        st.caption("Sources: " + ", ".join(d["sources"]))
                    st.divider()

            if not all_answered:
                st.info("Please answer all questions before grading.")


# ================= SECURITY & API =================
with tab3:
    st.subheader("Security & Local API")
    st.markdown(
        """
This app is designed to stay **local**:

- Notes & lecture slides: `data/`
- Vector DB: `data/vectordb/`
- Audit log: `data/logs/app_events.csv`
- UI: `http://localhost:8501`
- API calls: `http://127.0.0.1:8000` (your own FastAPI)

Nothing is sent to the internet by default.
        """
    )

    st.markdown("### 1. Local audit log")
    st.code("data/logs/app_events.csv", language="text")
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, "rb") as f:
            st.download_button(
                "Download audit log", data=f.read(), file_name="app_events.csv"
            )

    st.markdown("### 2. Call local FastAPI (http://127.0.0.1:8000/explain)")
    api_term = st.text_input("Term to ask the local API about:", "firewall")
    if st.button("Call local API"):
        try:
            r = requests.post(
                "http://127.0.0.1:8000/explain",
                json={"term": api_term},
                timeout=5,
            )
            data = r.json()
            st.success("Response from local API:")
            st.json(data)
            log_event("local_api_call", f"term={api_term}")
        except Exception as e:
            st.error(
                f"Could not reach local API on 127.0.0.1:8000 — is api_server.py running? ({e})"
            )
            st.info("Run this in another terminal: `uvicorn api_server:app --reload --port 8000`")
