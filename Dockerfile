FROM python:3.13-slim
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend ./backend
COPY frontend/dist ./frontend/dist
ENV DATABASE_URL=sqlite:///./nova_cart.db
ENV ENV=production
EXPOSE 8000
WORKDIR /app/backend
CMD ["sh","-c","python scripts_seed.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
