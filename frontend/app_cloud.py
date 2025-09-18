# frontend/app_cloud.py
# Single-process Streamlit app for Cloud (no FastAPI). Seeds SQLite/Chroma once,
# then imports the shared backend agent and answers queries.

import os
import re
import time
import sqlite3
import pandas as pd
import streamlit as st

# ------------------ Secrets / ENV ------------------
# Put OPENAI_API_KEY in Streamlit Cloud → Settings → Secrets
if "OPENAI_API_KEY" in st.secrets:
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]

# Disable file watchers (avoid inotify limit on Streamlit Cloud)
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"

# Neutralize proxy envs that might bleed into clients
for _v in ["HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy", "OPENAI_PROXY"]:
    os.environ.pop(_v, None)

# Make sure storage dirs exist
os.makedirs("storage", exist_ok=True)
os.makedirs("storage/chroma", exist_ok=True)

# ------------------ One-off bootstrap ------------------
@st.cache_resource(show_spinner=False)
def bootstrap_resources() -> bool:
    """Ensure SQLite is seeded and Chroma has docs (glossary/interventions)."""
    # 1) seed SQLite if empty
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

    # 2) build Chroma vector store if empty (use local FastEmbed embeddings)
    from langchain_community.embeddings import FastEmbedEmbeddings
    from langchain_community.vectorstores import Chroma

    DOCS = {
        "glossary.txt": (
            "Over-exploited: Annual groundwater extraction exceeds annual recharge; strict regulation and "
            "recharge are needed.\n"
            "Critical: Extraction close to recharge; adopt conservation and artificial recharge "
            "(check-dams, percolation tanks).\n"
            "Safe: Extraction comfortably below recharge. Monitor and use efficient irrigation practices."
        ),
        "interventions.txt": (
            "Interventions:\n"
            "- Check-dams and percolation tanks in upper catchments.\n"
            "- Roof-top rainwater harvesting in settlements and public buildings.\n"
            "- Water budgeting at panchayat level; crop planning to reduce water stress.\n"
            "Citations: CGWB GWRA-2022; Master Plan for Artificial Recharge 2020."
        ),
    }

    emb = FastEmbedEmbeddings()  # local, small, no API/proxy issues
    vs = Chroma(persist_directory="storage/chroma", embedding_function=emb)
    try:
        existing = vs._collection.count() if hasattr(vs._collection, "count") else 0
    except Exception:
        existing = 0
    if existing == 0:
        texts = list(DOCS.values())
        metas = [{"source": k} for k in DOCS.keys()]
        Chroma.from_texts(texts, metadatas=metas, embedding=emb, persist_directory="storage/chroma").persist()
    return True

bootstrap_resources()  # runs once per server

# ------------------ Import agent (uses same storage) ------------------
from backend.agent import ask_agent  # shared logic, uses SQLite+Chroma

# ------------------ UI helpers ------------------
def extract_table(md_text: str):
    mtab = re.search(r"Year\s*\|\s*Level\s*\(m\)\s*\n-+\s*\|\s*-+\s*\n(.+?)(?:\n\n|\Z)", md_text, re.S)
    if not mtab:
        return None
    body = mtab.group(1).strip()
    rows = []
    for line in body.splitlines():
        if "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2:
            try:
                rows.append((int(parts[0]), float(parts[1])))
            except:
                pass
    if not rows:
        return None
    return pd.DataFrame(rows, columns=["Year", "Level (m)"]).sort_values("Year")

def slope_from_df(df: pd.DataFrame):
    if df is None or len(df) < 2:
        return None
    df = df.sort_values("Year")
    y0, y1 = df["Year"].iloc[0], df["Year"].iloc[-1]
    v0, v1 = df["Level (m)"].iloc[0], df["Level (m)"].iloc[-1]
    yrs = max(1, (y1 - y0))
    return (v1 - v0) / yrs

def stage_badge(md_text: str):
    if re.search(r"over[- ]?exploited", md_text, re.I): return "Over-exploited", "crit"
    if re.search(r"\bcritical\b", md_text, re.I):       return "Critical", "warn"
    if re.search(r"semi[- ]?critical", md_text, re.I):  return "Semi-critical", "warn"
    if re.search(r"\bsafe\b", md_text, re.I):           return "Safe", "ok"
    return None, None

# ------------------ UI ------------------
st.set_page_config(page_title="NeerSetu – Cloud", page_icon="💧", layout="wide")
st.title("💧 NeerSetu – INGRES AI Copilot (Cloud)")
st.caption("Single-process Streamlit app (no FastAPI).")

examples = [
    "2015–2024 groundwater trend for Block A?",
    "Stage of extraction for Block B in 2022?",
    "Compare 2019 vs 2024 groundwater level for Block A.",
    "What does over-exploited mean and what should we do?",
]
ex_cols = st.columns(len(examples))
for i, ex in enumerate(examples):
    if ex_cols[i].button(ex, key=f"ex_{i}"):
        st.session_state["q"] = ex

q = st.text_input("Ask a question (Hi/En)", value=st.session_state.get("q", "2015–2024 groundwater trend for Block A?"))
if st.button("Ask"):
    with st.spinner("Thinking..."):
        t0 = time.time()
        ans = ask_agent(q)
        t1 = time.time()
    st.markdown(f"_Latency: {int(1000 * (t1 - t0))} ms_")

    # Stage badge
    s, cls = stage_badge(ans)
    st.write(f"**Stage:** {s or 'n/a'}")

    # Table + chart + Δ
    df = extract_table(ans)
    if df is not None:
        sl = slope_from_df(df)
        st.metric("Δ (m/yr)", f"{sl:+.2f}" if sl is not None else "—")
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.line_chart(df.set_index("Year")["Level (m)"])

    # Raw answer
    st.markdown(ans)
