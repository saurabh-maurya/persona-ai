import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import get_settings

_bearer = HTTPBearer(auto_error=False)


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    settings = get_settings()
    token = credentials.credentials if credentials else None
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token")
