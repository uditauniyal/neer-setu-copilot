from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from backend.agent import ask_agent

app = FastAPI(title="NeerSetu API", version="0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

class AskRequest(BaseModel):
    query: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/ask")
def ask(req: AskRequest):
    return {"answer": ask_agent(req.query)}
