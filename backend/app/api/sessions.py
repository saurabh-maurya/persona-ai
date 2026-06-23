from fastapi import APIRouter, HTTPException, Request
from app.schemas.session import SessionCreate, SessionResponse
from app.services.session_service import SessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _service(request: Request) -> SessionService:
    return SessionService(request.app.state.db)


@router.post("", status_code=201)
async def create_session(body: SessionCreate, request: Request):
    try:
        return await _service(request).create(body)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("")
async def list_sessions(request: Request, limit: int = 50):
    return await _service(request).get_all(limit=limit)


@router.get("/{id}")
async def get_session(id: str, request: Request):
    session = await _service(request).get_by_id(id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session


@router.get("/character/{character_id}")
async def get_sessions_by_character(character_id: str, request: Request):
    return await _service(request).get_by_character(character_id)


@router.delete("/{id}", status_code=204)
async def delete_session(id: str, request: Request):
    deleted = await _service(request).delete(id)
    if not deleted:
        raise HTTPException(404, "Session not found")
