#!/usr/bin/env bash
set -e
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp -n .env.sample .env || true

python backend/data/create_db.py
python ingest_docs.py

( uvicorn backend.main:app --host 0.0.0.0 --port 8000 & )
API_BASE=http://127.0.0.1:8000 streamlit run frontend/app.py
