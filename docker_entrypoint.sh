#!/usr/bin/env bash
set -e
python backend/data/create_db.py
python ingest_docs.py
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
API_BASE=http://127.0.0.1:8000 streamlit run frontend/app.py --server.port=8501 --server.address=0.0.0.0
