import secrets
import datetime
import jwt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(body: LoginRequest):
    settings = get_settings()
    username_ok = secrets.compare_digest(body.username, settings.admin_username)
    password_ok = secrets.compare_digest(body.password, settings.admin_password)
    if not (username_ok and password_ok):
        raise HTTPException(401, "Invalid credentials")
    payload = {
        "sub": body.username,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=settings.jwt_expiry_hours),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return {"token": token, "username": body.username}


@router.post("/logout")
async def logout():
    return {"ok": True}


@router.get("/me")
async def me(token: str = ""):
    """Used by frontend to validate a stored token."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return {"username": payload["sub"]}
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
