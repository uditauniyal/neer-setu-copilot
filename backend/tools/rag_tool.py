import os
from dotenv import load_dotenv
load_dotenv()
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

class RAGStore:
    def __init__(self, persist_dir="storage/chroma"):
        self.emb = OpenAIEmbeddings(model=os.getenv("EMBED_MODEL","text-embedding-3-small"))
        self.vs = Chroma(persist_directory=persist_dir, embedding_function=self.emb)

    def search_policy(self, query: str, k: int = 3) -> str:
        docs = self.vs.similarity_search(query, k=k)
        if not docs:
            return "No policy passages found."
        out = []
        for d in docs:
            src = d.metadata.get("source","doc")
            out.append(f"- {d.page_content.strip()}  \n  (source: {src})")
        return "Relevant policy passages:\n" + "\n".join(out)

rag_store = RAGStore() 
