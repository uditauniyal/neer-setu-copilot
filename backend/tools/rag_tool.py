# backend/tools/rag_tool.py
# Minimal, zero-dependency keyword retriever for Cloud (no embeddings/Chroma).

import os
from dotenv import load_dotenv

load_dotenv()

# Neutralize proxy envs for safety
for _v in ["HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy", "OPENAI_PROXY"]:
    os.environ.pop(_v, None)

# Tiny in-memory corpus
_DOCS = [
    {
        "source": "glossary.txt",
        "text": (
            "Over-exploited: Annual groundwater extraction exceeds annual recharge; strict regulation and "
            "recharge are needed. Critical: Extraction close to recharge; adopt conservation and artificial "
            "recharge (check-dams, percolation tanks). Safe: Extraction comfortably below recharge. "
            "Monitor and use efficient irrigation practices."
        ),
    },
    {
        "source": "interventions.txt",
        "text": (
            "Interventions: Check-dams and percolation tanks in upper catchments; roof-top rainwater "
            "harvesting in settlements and public buildings; water budgeting at panchayat level; crop "
            "planning to reduce water stress. Citations: CGWB GWRA-2022; Master Plan for Artificial "
            "Recharge 2020."
        ),
    },
]

def _score(query: str, text: str) -> int:
    # Simple keyword score: count of unique query tokens present
    q = [t for t in query.lower().split() if len(t) >= 3]
    t = text.lower()
    return sum(1 for tok in set(q) if tok in t)

class RAGStore:
    def __init__(self):
        self.docs = _DOCS

    def search(self, query: str, k: int = 3):
        scored = sorted(
            [{"text": d["text"], "source": d["source"], "score": _score(query, d["text"])} for d in self.docs],
            key=lambda x: x["score"],
            reverse=True,
        )
        top = [ {"text": s["text"], "source": s["source"]} for s in scored if s["score"] > 0 ][:k]
        return top

    # Backward-compatible string formatter (unused by final agent but safe to keep)
    def search_policy(self, query: str, k: int = 3) -> str:
        hits = self.search(query, k=k)
        if not hits:
            return "No policy passages found."
        return "Relevant policy passages:\n" + "\n".join(f"- {h['text']}  \n  (source: {h['source']})" for h in hits)

rag_store = RAGStore()
