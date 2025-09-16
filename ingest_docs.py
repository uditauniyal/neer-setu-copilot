import os, glob
from dotenv import load_dotenv
load_dotenv()
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

os.makedirs("storage/chroma", exist_ok=True)
docs = []
metas = []
for path in glob.glob("docs/*.txt"):
    with open(path, "r", encoding="utf-8") as f:
        docs.append(f.read())
        metas.append({"source": os.path.basename(path)})

emb = OpenAIEmbeddings(model=os.getenv("EMBED_MODEL","text-embedding-3-small"))
vs = Chroma.from_texts(texts=docs, metadatas=metas, embedding=emb,
                       persist_directory="storage/chroma")
vs.persist()
print("Ingested docs into Chroma at storage/chroma")
