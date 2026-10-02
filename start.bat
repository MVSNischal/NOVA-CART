@echo off
setlocal
cd /d "%~dp0"
python -m pip install -r backend\requirements.txt
cd backend
python scripts_seed.py
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
