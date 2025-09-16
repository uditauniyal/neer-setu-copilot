@echo off
for /f "tokens=1,2 delims==" %%a in (.env.sample) do (
    if "%%a"=="OPENAI_API_KEY" (
        set "%%a=%%b"
    )
)
python -m venv .venv
call .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
copy /Y .env.sample .env

python backend\data\create_db.py
python ingest_docs.py

start cmd /k uvicorn backend.main:app --host 0.0.0.0 --port 8000
set API_BASE=http://127.0.0.1:8000
streamlit run frontend\app.py
