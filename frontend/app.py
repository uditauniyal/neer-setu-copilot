# frontend/app.py
import os
import re
import time
import requests
import pandas as pd
import streamlit as st

# ---------------- Config ----------------
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")
APP_TITLE = "NeerSetu – INGRES AI Copilot"
APP_TAGLINE = "Ask groundwater questions (trends, stage, interventions) in Hindi/English."

# ---------------- Style ----------------
st.set_page_config(page_title=APP_TITLE, page_icon="💧", layout="wide")
st.markdown(
    """
    <style>
    .neer-header {font-size: 1.8rem; font-weight: 700; margin-bottom: 0.25rem;}
    .neer-sub   {color:#64748b; margin-bottom: 1rem;}
    .badge {display:inline-block;padding:.25rem .5rem;border-radius:12px;font-size:.75rem;margin-right:.25rem;background:#e2f2ff;color:#0369a1;border:1px solid #bae6fd;}
    .chip  {display:inline-block;padding:.35rem .6rem;border-radius:16px;font-size:.80rem;margin:.25rem; background:#f1f5f9; border:1px solid #e2e8f0; cursor:pointer;}
    .ok    {background:#ecfdf5;border-color:#d1fae5;color:#065f46;}
    .warn  {background:#fff7ed;border-color:#ffedd5;color:#9a3412;}
    .crit  {background:#fef2f2;border-color:#fee2e2;color:#991b1b;}
    .small-note{color:#64748b;font-size:.85rem}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------- Helpers ----------------
def call_api(query: str) -> str:
    r = requests.post(f"{API_BASE}/ask", json={"query": query}, timeout=60)
    r.raise_for_status()
    return r.json().get("answer", "")

def extract_tiny_table(md_text: str):
    """
    Prefer the tiny markdown table. If absent, fallback to bullet-list parsing.
    """
    # ---- Try markdown table ----
    mtab = re.search(
        r"Year\s*\|\s*Level\s*\(m\)\s*\n-+\s*\|\s*-+\s*\n(.+?)(?:\n\n|\Z)",
        md_text, re.S
    )
    rows = []
    if mtab:
        body = mtab.group(1).strip()
        for line in body.splitlines():
            if "|" not in line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2:
                try:
                    year = int(parts[0]); level = float(parts[1])
                    rows.append((year, level))
                except:
                    pass
        if rows:
            return pd.DataFrame(rows, columns=["Year", "Level (m)"]).sort_values("Year")

    # ---- Fallback bullets ----
    bullets = re.findall(r"(?m)^\s*[-*•o]\s*(20\d{2})\D+(\d+(?:\.\d+)?)", md_text)
    if bullets:
        try:
            rows = [(int(y), float(v)) for (y, v) in bullets]
            return pd.DataFrame(rows, columns=["Year", "Level (m)"]).sort_values("Year")
        except:
            return None

    return None

def compute_slope_from_df(df: pd.DataFrame):
    """Compute Δ m/yr from parsed table."""
    if df is None or df.empty or len(df) < 2:
        return None
    df = df.sort_values("Year")
    y0, y1 = df["Year"].iloc[0], df["Year"].iloc[-1]
    v0, v1 = df["Level (m)"].iloc[0], df["Level (m)"].iloc[-1]
    yrs = max(1, (y1 - y0))
    return (v1 - v0) / yrs

def extract_citations(md_text: str):
    m = re.search(r"\*\*Citations:\*\*\s*(.+)$", md_text, re.S)
    if not m:
        return []
    raw = m.group(1).strip()
    parts = [p.strip() for p in re.split(r"\s*\|\s*", raw)]
    return [p for p in parts if p]

def detect_stage(md_text: str):
    if re.search(r"over[- ]?exploited", md_text, re.I):
        return "Over-exploited", "crit"
    if re.search(r"\bcritical\b", md_text, re.I):
        return "Critical", "warn"
    if re.search(r"semi[- ]?critical", md_text, re.I):
        return "Semi-critical", "warn"
    if re.search(r"\bsafe\b", md_text, re.I):
        return "Safe", "ok"
    return None, None

def lang_suffix(selected: str):
    if selected == "Auto": return ""
    if selected == "English": return " Answer in English."
    if selected == "Hindi (हिन्दी)": return " उत्तर हिन्दी में दें।"
    return ""

# ---------------- Sidebar ----------------
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    lang = st.radio("Answer language", ["Auto", "English", "Hindi (हिन्दी)"], index=0)
    st.markdown("---")
    st.markdown("### ℹ️ About")
    st.markdown(
        "- **Project:** NeerSetu – INGRES AI Copilot  \n"
        "- **PS:** SIH25066 (MoJS)  \n"
        "- **Stack:** FastAPI · LangChain · OpenAI · ChromaDB · SQLite"
    )
    st.markdown("---")
    if st.button("🧽 Clear session"):
        st.session_state.clear()
        st.rerun()

# ---------------- Header ----------------
st.markdown(f"<div class='neer-header'>💧 {APP_TITLE}</div>", unsafe_allow_html=True)
st.markdown(f"<div class='neer-sub'>{APP_TAGLINE}</div>", unsafe_allow_html=True)
st.markdown(
    "<span class='badge'>PS: SIH25066</span> <span class='badge'>Environment & Governance</span> "
    "<span class='badge'>Text-only MVP</span>",
    unsafe_allow_html=True,
)
st.markdown("")

# ---------------- Example Chips ----------------
examples = [
    "2015–2024 groundwater trend for Block A?",
    "Stage of extraction for Block B in 2022?",
    "Compare 2019 vs 2024 groundwater level for Block A.",
    "What does over-exploited mean and what should we do?",
]
st.write("**Examples:**")
cols = st.columns(len(examples))
for i, ex in enumerate(examples):
    if cols[i].button(ex, key=f"ex_{i}"):
        st.session_state["prefill"] = ex

# ---------------- Input ----------------
default_q = st.session_state.get("prefill", "")
q = st.text_area("Your question", value=default_q, placeholder="e.g., 2015–2024 groundwater trend for Block A?")
go = st.button("Ask", type="primary")

# ---------------- Chat history ----------------
if "history" not in st.session_state:
    st.session_state["history"] = []  # list of dicts: {q, answer, t_ms}

def render_answer(answer_md: str):
    # Stage badge
    stage, stage_class = detect_stage(answer_md)

    # Parse tiny table & compute Δ
    df = extract_tiny_table(answer_md)
    slope = compute_slope_from_df(df)

    # Metrics/top row
    mcol = st.columns(3)
    mcol[0].metric("LLM Compose", "OK", delta=None)
    mcol[1].metric("Δ (m/yr)", f"{slope:+.2f}" if slope is not None else "—")
    if stage:
        mcol[2].markdown(f"<div class='badge {stage_class}'>{stage}</div>", unsafe_allow_html=True)
    else:
        mcol[2].markdown(f"<div class='badge'>Stage: n/a</div>", unsafe_allow_html=True)

    # Parsed table + chart
    if df is not None and not df.empty:
        st.markdown("**Last years (parsed)**")
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.line_chart(df.set_index("Year")["Level (m)"])

    # Raw answer
    st.markdown("**Answer**")
    st.markdown(answer_md)

    # Citations
    cites = extract_citations(answer_md)
    if cites:
        with st.expander("Citations", expanded=False):
            for c in cites:
                st.write("• " + c)

if go and q.strip():
    user_q = q.strip() + lang_suffix(lang)
    with st.spinner("Consulting tools and composing answer..."):
        t0 = time.time()
        try:
            answer_md = call_api(user_q)
        except requests.HTTPError as e:
            st.error(f"API error: {e.response.status_code} {e.response.text}")
            st.stop()
        t1 = time.time()
    st.session_state["history"].append({"q": q.strip(), "answer": answer_md, "t_ms": int(1000 * (t1 - t0))})

# ---------------- Render history ----------------
if st.session_state["history"]:
    st.markdown("### History")
    for i, item in enumerate(reversed(st.session_state["history"])):
        with st.container(border=True):
            st.markdown(
                f"**Q:** {item['q']}  \n<span class='small-note'>Latency: {item['t_ms']} ms</span>",
                unsafe_allow_html=True,
            )
            render_answer(item["answer"])
else:
    st.info("Ask a question or click an example to get started.")
