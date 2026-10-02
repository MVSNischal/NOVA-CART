from functools import lru_cache
from pydantic import BaseModel, Field
import os

class Settings(BaseModel):
    app_name: str = "Nova Cart"
    env: str = os.getenv("ENV", "development")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./nova_cart.db")
    session_cookie: str = "nova_session"
    csrf_cookie: str = "nova_csrf"
    session_ttl_seconds: int = int(os.getenv("SESSION_TTL_SECONDS", "86400"))
    upload_dir: str = os.getenv("UPLOAD_DIR", "./private_uploads")
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    allowed_origins: list[str] = Field(default_factory=lambda: os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(","))
    mock_mode: bool = os.getenv("MOCK_MODE", "true").lower() == "true"
    secret_key: str = os.getenv("SECRET_KEY", "dev-only-change-me")

@lru_cache
def get_settings() -> Settings:
    return Settings()
