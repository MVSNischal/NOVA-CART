from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.auth import current_user
from app.core.security import ensure_csrf

def db_dep(): return Depends(get_db)

def get_current_user(request:Request, db:Session=Depends(get_db)):
    user = current_user(db, request.cookies.get("nova_session"))
    if not user: raise HTTPException(401, detail={"code":"AUTH_REQUIRED","message":"Please sign in"})
    ensure_csrf(request)
    return user

def require_roles(*roles):
    def checker(user=Depends(get_current_user)):
        if user.role not in roles: raise HTTPException(403, detail={"code":"FORBIDDEN","message":"Insufficient permission"})
        return user
    return checker
