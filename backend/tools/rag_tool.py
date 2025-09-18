# backend/tools/rag_tool.py
# Minimal, zero-dependency keyword retriever for Cloud (no embeddings/Chroma).

import os
from dotenv import load_dotenv
load_dotenv()

for _v in ["HTTP_PROXY","http_proxy","HTTPS_PROXY","https_proxy","ALL_PROXY","all_proxy","OPENAI_PROXY"]:
    os.environ.pop(_v, None)

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
            "planning to reduce water stress. Citations: CGWB GWRA-2022; Master Plan 2020."
        ),
    },
]

def _score(q: str, t: str) -> int:
    toks = [w for w in q.lower().split() if len(w) >= 3]
    T = t.lower()
    return sum(1 for tok in set(toks) if tok in T)

class RAGStore:
    def __init__(self):
        self.docs = _DOCS

    def search(self, query: str, k: int = 3):
        ranked = sorted(
            [{"text": d["text"], "source": d["source"], "score": _score(query, d["text"])}
             for d in self.docs],
            key=lambda x: x["score"], reverse=True
        )
        return [{"text": r["text"], "source": r["source"]} for r in ranked if r["score"] > 0][:k]

    def search_policy(self, query: str, k: int = 3) -> str:
        hits = self.search(query, k=k)
        if not hits: return "No policy passages found."
        return "Relevant policy passages:\n" + "\n".join(
            f"- {h['text']}  \n  (source: {h['source']})" for h in hits
        )

rag_store = RAGStore()
