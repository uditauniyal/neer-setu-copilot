# backend/tools/rag_tool.py
import os
from dotenv import load_dotenv

load_dotenv()

# Neutralize proxy envs that can pass unsupported 'proxies' to OpenAI client
for _v in ["HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy", "OPENAI_PROXY"]:
    os.environ.pop(_v, None)

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma


class RAGStore:
    def __init__(self, persist_dir: str = "storage/chroma"):
        self.emb = OpenAIEmbeddings(
            model=os.getenv("EMBED_MODEL", "text-embedding-3-small"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_proxy=None,
        )
        self.vs = Chroma(persist_directory=persist_dir, embedding_function=self.emb)

    # Preferred by backend.agent (returns structured hits)
    def search(self, query: str, k: int = 3):
        docs = self.vs.similarity_search(query, k=k)
        return [{"text": d.page_content.strip(), "source": d.metadata.get("source", "doc")} for d in docs]

    # Backward-compatible (not used by current agent, but safe to keep)
    def search_policy(self, query: str, k: int = 3) -> str:
        docs = self.vs.similarity_search(query, k=k)
        if not docs:
            return "No policy passages found."
        out = []
        for d in docs:
            src = d.metadata.get("source", "doc")
            out.append(f"- {d.page_content.strip()}  \n  (source: {src})")
        return "Relevant policy passages:\n" + "\n".join(out)


rag_store = RAGStore()
