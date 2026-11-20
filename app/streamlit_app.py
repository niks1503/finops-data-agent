"""Chat-style UI for the FinOps agent: streamlit run app/streamlit_app.py"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from finops_agent.agent import FinOpsAgent  # noqa: E402

EXAMPLES = [
    "Which account spent the most last month?",
    "In September 2026, which account and service had the biggest month-over-month % increase?",
    "Show monthly Vertex AI spend for ml-research.",
    "Which regions did payments-dev use in October 2026?",
]

st.set_page_config(page_title="FinOps Data Agent", page_icon="💸", layout="wide")
st.title("FinOps Data Agent")
st.caption("Ask questions about multi-cloud cost data. The agent writes and runs read-only SQL, fixes its own errors, "
           "and answers only from query results.")


@st.cache_resource
def load_agent() -> FinOpsAgent:
    return FinOpsAgent()


try:
    agent = load_agent()
except RuntimeError as exc:
    st.error(str(exc))
    st.stop()

cols = st.columns(len(EXAMPLES))
for col, ex in zip(cols, EXAMPLES):
    if col.button(ex, use_container_width=True):
        st.session_state["q"] = ex

question = st.text_input("Your question", key="q", placeholder="Why did storage spend jump in September?")
if question:
    with st.spinner("Thinking, querying, checking..."):
        r = agent.ask(question)
    st.markdown(f"### {r.answer}")
    if r.error:
        st.warning(r.error)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Latency", f"{r.latency_s:.1f}s")
    m2.metric("SQL attempts", r.sql_attempts, delta=f"{r.sql_errors} fixed" if r.sql_errors else None)
    m3.metric("Tokens", r.input_tokens + r.output_tokens)
    m4.metric("Model", r.model)
    if r.rows:
        df = pd.DataFrame(r.rows, columns=r.columns)
        numeric = df.select_dtypes("number").columns
        if len(df) > 1 and len(numeric) == 1 and len(df.columns) == 2:
            st.bar_chart(df.set_index(df.columns[0])[numeric[0]])
        st.dataframe(df, use_container_width=True)
    if r.sql:
        with st.expander("SQL the agent ran"):
            st.code(r.sql, language="sql")
    with st.expander("Agent steps"):
        st.json(r.steps)
