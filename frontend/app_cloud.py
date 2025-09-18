# frontend/app_cloud.py
# Streamlit Cloud entry — single process (no FastAPI, no embeddings/Chroma).
# - Seeds SQLite once
# - Imports backend.agent.ask_agent (which now has a local fallback when LLM fails)
# - Polished UI + Diagnostics panel to verify OPENAI_API_KEY on cloud

import os, sys, re, time, sqlite3, pandas as pd
from pathlib import Path

# ---------- make project root importable ----------
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

# ------------------ ENV/Secrets ------------------
if "OPENAI_API_KEY" in st.secrets:
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]

os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"
for _v in ["HTTP_PROXY","http_proxy","HTTPS_PROXY","https_proxy","ALL_PROXY","all_proxy","OPENAI_PROXY"]:
    os.environ.pop(_v, None)

# ------------------ storage ------------------
os.makedirs("storage", exist_ok=True)

@st.cache_resource(show_spinner=False)
def bootstrap_resources() -> bool:
    db_path = "storage/neersetu.db"
    conn = sqlite3.connect(db_path); cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS gw_levels(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        state TEXT, district TEXT, block TEXT,
        year INTEGER, level_m REAL, stage TEXT
    );""")
    cnt = cur.execute("SELECT COUNT(*) FROM gw_levels").fetchone()[0]
    if cnt == 0:
        rows = [
            ("SampleState","SampleDistrict","Block A",2015,12.1,"Safe"),
            ("SampleState","SampleDistrict","Block A",2016,12.6,"Safe"),
            ("SampleState","SampleDistrict","Block A",2017,13.2,"Semi-critical"),
            ("SampleState","SampleDistrict","Block A",2018,13.9,"Semi-critical"),
            ("SampleState","SampleDistrict","Block A",2019,14.7,"Critical"),
            ("SampleState","SampleDistrict","Block A",2020,15.5,"Critical"),
            ("SampleState","SampleDistrict","Block A",2021,16.5,"Over-exploited"),
            ("SampleState","SampleDistrict","Block A",2022,17.2,"Over-exploited"),
            ("SampleState","SampleDistrict","Block A",2023,17.9,"Over-exploited"),
            ("SampleState","SampleDistrict","Block A",2024,18.4,"Over-exploited"),
            ("SampleState","SampleDistrict","Block B",2015,8.5,"Safe"),
            ("SampleState","SampleDistrict","Block B",2016,8.6,"Safe"),
            ("SampleState","SampleDistrict","Block B",2017,8.8,"Safe"),
            ("SampleState","SampleDistrict","Block B",2018,8.9,"Safe"),
            ("SampleState","SampleDistrict","Block B",2019,9.1,"Safe"),
            ("SampleState","SampleDistrict","Block B",2020,9.3,"Safe"),
            ("SampleState","SampleDistrict","Block B",2021,9.6,"Safe"),
            ("SampleState","SampleDistrict","Block B",2022,9.7,"Safe"),
            ("SampleState","SampleDistrict","Block B",2023,9.8,"Safe"),
            ("SampleState","SampleDistrict","Block B",2024,10.0,"Safe"),
        ]
        cur.executemany("""INSERT INTO gw_levels(state,district,block,year,level_m,stage)
                           VALUES(?,?,?,?,?,?)""", rows)
        conn.commit()
    conn.close()
    return True

bootstrap_resources()

# ------------------ import agent (has local fallback if key missing) ------------------
from backend.agent import ask_agent

# ------------------ helpers ------------------
def extract_table(md_text: str):
    mtab = re.search(r"Year\s*\|\s*Level\s*\(m\)\s*\n-+\s*\|\s*-+\s*\n(.+?)(?:\n\n|\Z)", md_text, re.S)
    if not mtab: return None
    body = mtab.group(1).strip()
    rows = []
    for line in body.splitlines():
        if "|" not in line: continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2:
            try: rows.append((int(parts[0]), float(parts[1])))
            except: pass
    if not rows: return None
    return pd.DataFrame(rows, columns=["Year","Level (m)"]).sort_values("Year")

def slope_from_df(df: pd.DataFrame):
    if df is None or len(df) < 2: return None
    df = df.sort_values("Year")
    y0,y1 = df["Year"].iloc[0], df["Year"].iloc[-1]
    v0,v1 = df["Level (m)"].iloc[0], df["Level (m)"].iloc[-1]
    yrs = max(1,(y1-y0))
    return (v1-v0)/yrs

def extract_citations(md_text: str):
    m = re.search(r"\*\*Citations:\*\*\s*(.+)$", md_text, re.S)
    if not m: return []
    raw = m.group(1).strip()
    parts = [p.strip() for p in re.split(r"\s*\|\s*", raw)]
    return [p for p in parts if p]

def stage_badge(md_text: str):
    if re.search(r"over[- ]?exploited", md_text, re.I): return "Over-exploited","crit"
    if re.search(r"\bcritical\b", md_text, re.I):       return "Critical","warn"
    if re.search(r"semi[- ]?critical", md_text, re.I):  return "Semi-critical","warn"
    if re.search(r"\bsafe\b", md_text, re.I):           return "Safe","ok"
    return None, None

def lang_suffix(selected: str):
    if selected == "Auto": return ""
    if selected == "English": return " Answer in English."
    if selected == "Hindi (हिन्दी)": return " उत्तर हिन्दी में दें।"
    return ""

def is_error_answer(ans: str) -> bool:
    s = ans.strip().lower()
    return ("authentication error" in s) or ("openai api error" in s) or ("llm error" in s)

# ------------------ Style ------------------
st.set_page_config(page_title="NeerSetu – Cloud", page_icon="💧", layout="wide")
st.markdown(
    """
    <style>
    .neer-header {font-size: 1.8rem; font-weight: 700; margin-bottom: 0.25rem;}
    .neer-sub   {color:#64748b; margin-bottom: 1rem;}
    .badge {display:inline-block;padding:.25rem .5rem;border-radius:12px;font-size:.75rem;margin-right:.25rem;background:#e2f2ff;color:#0369a1;border:1px solid #bae6fd;}
    .ok    {background:#ecfdf5;border-color:#d1fae5;color:#065f46;}
    .warn  {background:#fff7ed;border-color:#ffedd5;color:#9a3412;}
    .crit  {background:#fef2f2;border-color:#fee2e2;color:#991b1b;}
    .small-note{color:#64748b;font-size:.85rem}
    .error-card{background:#ffe8e8;padding:1rem;border-radius:.5rem;border:1px solid #fecaca;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------ Sidebar (with Diagnostics) ------------------
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    lang = st.radio("Answer language", ["Auto", "English", "Hindi (हिन्दी)"], index=0)
    st.markdown("---")
    st.markdown("### 🔎 Diagnostics")
    masked = (os.getenv("OPENAI_API_KEY","")[:4] + "…" + os.getenv("OPENAI_API_KEY","")[-4:]) if os.getenv("OPENAI_API_KEY") else "None"
    st.caption(f"OPENAI_API_KEY: **{masked}**")
    if st.button("Clear server cache"):
        st.cache_resource.clear()
        st.success("Server cache cleared. Click Rerun.")
    st.markdown("---")
    st.markdown("### ℹ️ About")
    st.markdown(
        "- **Project:** NeerSetu – INGRES AI Copilot  \n"
        "- **PS:** SIH25066 (MoJS)  \n"
        "- **Stack:** Streamlit (Cloud) · OpenAI client · SQLite · Keyword RAG"
    )

# ------------------ Header ------------------
st.markdown(f"<div class='neer-header'>💧 NeerSetu – INGRES AI Copilot (Cloud)</div>", unsafe_allow_html=True)
st.markdown(f"<div class='neer-sub'>Ask groundwater questions (trends, stage, interventions) in Hindi/English.</div>", unsafe_allow_html=True)
st.markdown("<span class='badge'>PS: SIH25066</span> <span class='badge'>Text-only MVP</span>", unsafe_allow_html=True)
st.markdown("")

# ------------------ Example Chips ------------------
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

# ------------------ Input ------------------
default_q = st.session_state.get("prefill", "2015–2024 groundwater trend for Block A?")
q = st.text_area("Your question", value=default_q, placeholder="e.g., 2015–2024 groundwater trend for Block A?")
go = st.button("Ask", type="primary")

# ------------------ Chat history ------------------
if "history" not in st.session_state:
    st.session_state["history"] = []  # list of dicts: {q, answer, t_ms}

def render_answer(answer_md: str):
    if is_error_answer(answer_md):
        st.markdown(f"<div class='error-card'>{answer_md}</div>", unsafe_allow_html=True)
        return

    # Stage badge
    stage, stage_class = stage_badge(answer_md)

    # Parse tiny table & compute Δ
    df = extract_table(answer_md)
    slope = slope_from_df(df)

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
        ans = ask_agent(user_q)  # uses LLM if key is valid, else local fallback
        t1 = time.time()
    st.session_state["history"].append({"q": q.strip(), "answer": ans, "t_ms": int(1000 * (t1 - t0))})

# ------------------ Render history ------------------
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
