# backend/agent.py
"""
NeerSetu – INGRES AI Copilot (cloud-safe)
- Tool-first (SQLite + keyword RAG) → LLM compose
- Compare path ("2019 vs 2024")
- Robust block parsing
- Strips mid-body 'Source:' lines; uses footer Citations
- ChatOpenAI constructed with openai_proxy=None (fixes proxies kw crash)
"""

import os, re
from dotenv import load_dotenv
load_dotenv()

# ---- neutralize any proxy envs before client creation ----
for _v in ["HTTP_PROXY","http_proxy","HTTPS_PROXY","https_proxy","ALL_PROXY","all_proxy","OPENAI_PROXY"]:
    os.environ.pop(_v, None)

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from backend.tools.sql_tool import get_trend, get_stage, get_level
from backend.tools.rag_tool import rag_store

# ---------------- LLM ----------------
LLM = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
    temperature=0,
    openai_api_key=os.getenv("OPENAI_API_KEY", ""),
    openai_proxy=None,            # <-- critical: disable proxy param path
    timeout=30,
)

SYSTEM = """You are NeerSetu, an INGRES groundwater copilot.
- Use tools (SQL/RAG) for facts before answering.
- Do NOT claim data was provided by the user/copilot.
- Always include 'Source' and 'Year(s)' when numbers/time-series appear.
- Do NOT put any 'Citations:' or 'Source:' lines in the body; the system appends a Citations footer.
- Answer in user's language (Hindi/English).
- Format: brief bullets + tiny table (if trend/comparison) + citations at end.
- If data is missing, say 'insufficient data' and suggest next steps.
"""
PROMPT = ChatPromptTemplate.from_messages([("system", SYSTEM), ("human", "{msg}")])

_FOOTER_RX = re.compile(r"\*\*Citations:\*\*", re.I)

def _detect_intent(q: str) -> str:
    ql = q.lower()
    years = re.findall(r"(20\d{2})", ql)
    if "compare" in ql or " vs " in ql or ql.startswith("compare "): return "compare"
    if "trend" in ql or ("from" in ql and "to" in ql) or len(years) >= 2: return "trend"
    if any(k in ql for k in ["stage","over-exploited","critical","safe"]):
        return "stage_lookup" if re.search(r"(20\d{2})", ql) else "definition"
    if any(k in ql for k in ["what","how","explain","meaning","क्या","कैसे"]): return "definition"
    return "mixed"

def _extract_block(q: str) -> str:
    m = re.search(r"(block\s+[a-z0-9\-]+)", q, re.I)
    if m:
        b = m.group(1).strip()
        b = re.sub(r"[^\w\- ]+$", "", b)
        m2 = re.match(r"block\s+([a-z0-9\-]+)", b, re.I)
        if m2:
            tok = m2.group(1).strip()
            return f"Block {tok.upper()}" if len(tok)==1 else f"Block {tok}".replace("Block block","Block ").title()
        return b.title()
    m = re.search(r"\bfor\s+([a-z])\b", q, re.I)
    if m: return f"Block {m.group(1).upper()}"
    return "Block A"

def _strip_spurious_body_sources(txt: str) -> str:
    m = _FOOTER_RX.search(txt)
    if m: body, footer = txt[:m.start()], txt[m.start():]
    else: body, footer = txt, ""
    body = re.sub(
        r"(?im)^\s*(?:[-*]\s*)?Citations\s*:\s*\n(?:[ \t]*[-*].*\n|[ \t]*\S.*\n)*?(?=\n\S|$)",
        "", body)
    body = re.sub(r"(?im)^\s*(?:[-*]\s*)?(?:Source|Sources)\s*:\s*.*(?:\n(?!\S)|$)", "", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return (body + ("\n\n" + footer if footer else "")).strip()

def ask_agent(query: str) -> str:
    intent = _detect_intent(query)
    block  = _extract_block(query)
    years  = [int(y) for y in re.findall(r"(20\d{2})", query)]

    tool_outputs, citations = [], []
    forced_table_md = ""

    # TREND
    if intent == "trend" and len(years) >= 2:
        sy, ey = years[0], years[1]
        out = get_trend(block, sy, ey)
        if out.get("ok"):
            tbl = "Year | Level (m)\n-----|----------\n" + "\n".join(
                f"{r['year']} | {r['level_m']:.2f}" for r in out["tiny_table"]
            )
            forced_table_md = tbl
            tool_outputs.append(f"Trend: Δ≈{out['slope_per_year']:+.2f} m/yr; latest stage {out['latest_stage']}.\n{tbl}")
            citations.append(f"Source: {out['source']}; Years: {out['start']}–{out['end']}")
        else:
            tool_outputs.append(out["msg"])

    # STAGE LOOKUP
    elif intent == "stage_lookup" and len(years) >= 1:
        y = years[0]
        out = get_stage(block, y)
        if out.get("ok"):
            tool_outputs.append(f"Stage for {block} in {y}: {out['stage']} (level {out['level_m']:.2f} m).")
            citations.append(f"Source: {out['source']}; Year: {y}")
        else:
            tool_outputs.append(out["msg"])

    # COMPARE
    elif intent == "compare" and len(years) >= 2:
        y1, y2 = years[0], years[1]
        v1, v2 = get_level(block, y1), get_level(block, y2)
        row1 = f"{y1} | {v1['level_m']:.2f}" if v1.get("ok") else f"{y1} | —"
        row2 = f"{y2} | {v2['level_m']:.2f}" if v2.get("ok") else f"{y2} | —"
        tbl  = "Year | Level (m)\n-----|----------\n" + "\n".join([row1, row2])
        forced_table_md = tbl
        tool_outputs.append("Comparison:\n" + tbl)
        if v1.get("ok"): citations.append(f"Source: {v1['source']}; Year: {y1}")
        if v2.get("ok"): citations.append(f"Source: {v2['source']}; Year: {y2}")
        if v1.get("ok") and v2.get("ok") and y2 > y1:
            slope = (v2["level_m"] - v1["level_m"]) / (y2 - y1)
            tool_outputs.append(f"Estimated Δ≈{slope:+.2f} m/yr over {y1}–{y2}.")
        if not (v1.get("ok") or v2.get("ok")):
            tool_outputs.append("insufficient data for requested years.")

    # RAG grounding (keyword retriever)
    try:
        rag_hits = rag_store.search(query, k=3)
    except Exception as e:
        rag_hits = []; tool_outputs.append(f"(RAG error suppressed: {e})")
    if rag_hits:
        tool_outputs.append("Policy:\n" + "\n".join(f"- {d['text']} (source: {d['source']})" for d in rag_hits))
        citations.extend(f"Doc: {d['source']}" for d in rag_hits)

    # Compose
    context = "\n\n".join(tool_outputs) if tool_outputs else "No tool output."
    user_block = (
        f"User: {query}\n\nContext from tools:\n{context}\n\n"
        "Compose a grounded answer. Do NOT include any 'Citations:' or 'Source:' "
        "lines in the body; the system will append the Citations footer."
    )
    messages = PROMPT.format_messages(msg=user_block)
    resp = LLM.invoke(messages)
    answer = resp.content.strip()

    # Clean & ensure table present
    answer = _strip_spurious_body_sources(answer)
    if forced_table_md and "Year | Level (m)" not in answer:
        answer += "\n\n**Tiny table**\n" + forced_table_md
    if citations:
        answer += "\n\n**Citations:** " + " | ".join(sorted(set(citations)))
    return answer
