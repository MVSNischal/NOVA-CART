#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python -m pip install -r backend/requirements.txt
(cd backend && python scripts_seed.py)
(cd frontend && npm install && npm run build)
cd backend
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
