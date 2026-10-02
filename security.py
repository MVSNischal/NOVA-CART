import base64, hashlib, hmac, secrets, time
from fastapi import HTTPException, Request, Response
from .config import get_settings

PASSWORD_N = 2**14
PASSWORD_R = 8
PASSWORD_P = 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=PASSWORD_N, r=PASSWORD_R, p=PASSWORD_P, dklen=64)
    return "scrypt$%s$%s" % (base64.urlsafe_b64encode(salt).decode(), base64.urlsafe_b64encode(dk).decode())


def verify_password(password: str, encoded: str) -> bool:
    try:
        _, salt_b64, digest_b64 = encoded.split("$", 2)
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        expected = base64.urlsafe_b64decode(digest_b64.encode())
        actual = hashlib.scrypt(password.encode(), salt=salt, n=PASSWORD_N, r=PASSWORD_R, p=PASSWORD_P, dklen=64)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_session_token() -> str:
    return secrets.token_urlsafe(48)


def set_session(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(settings.session_cookie, token, httponly=True, secure=settings.env == "production", samesite="lax", max_age=settings.session_ttl_seconds, path="/")


def clear_session(response: Response) -> None:
    response.delete_cookie(get_settings().session_cookie, path="/")


def csrf_token() -> str:
    return secrets.token_urlsafe(24)


def ensure_csrf(request: Request) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    cookie = request.cookies.get(get_settings().csrf_cookie)
    header = request.headers.get("X-CSRF-Token")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise HTTPException(status_code=403, detail={"code":"CSRF_INVALID","message":"CSRF validation failed"})


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
