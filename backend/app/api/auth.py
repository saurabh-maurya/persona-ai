import datetime
import bcrypt
import jwt
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr
from app.config import get_settings
from app.repositories.user_repository import UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, request: Request):
    repo = UserRepository(request.app.state.db)

    if len(body.username) < 3:
        raise HTTPException(400, "Username must be at least 3 characters")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    if await repo.find_by_username(body.username):
        raise HTTPException(409, "Username already taken")
    if await repo.find_by_email(body.email):
        raise HTTPException(409, "Email already registered")

    password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()

    user_doc = {
        "_id": ObjectId(),
        "username": body.username,
        "email": body.email,
        "password_hash": password_hash,
        "approved": "N",
        "createdAt": datetime.datetime.utcnow(),
    }
    await request.app.state.db.users.insert_one(user_doc)
    return {"message": "Registration successful. Your account is pending approval by the administrator."}


@router.post("/login")
async def login(body: LoginRequest, request: Request):
    repo = UserRepository(request.app.state.db)
    user = await repo.find_by_username(body.username)

    if not user or not bcrypt.checkpw(body.password.encode(), user["password_hash"].encode()):
        raise HTTPException(401, "Invalid username or password")

    if user.get("approved", "N") != "Y":
        raise HTTPException(403, "Your account is pending approval. Please contact the administrator.")

    settings = get_settings()
    payload = {
        "sub": str(user["_id"]),
        "username": user["username"],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=settings.jwt_expiry_hours),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return {"token": token, "username": user["username"]}


@router.post("/logout")
async def logout():
    return {"ok": True}


@router.get("/me")
async def me(token: str = ""):
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return {"username": payload.get("username", ""), "userId": payload["sub"]}
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
