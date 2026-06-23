from fastapi import APIRouter, Request, Depends
from app.repositories.character_repository import CharacterRepository
from app.repositories.batch_repository import BatchRepository
from app.services.gemini_service import GeminiService
from app.dependencies import require_auth

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def dashboard(request: Request, current_user: str = Depends(require_auth)):
    db = request.app.state.db
    char_repo = CharacterRepository(db)
    batch_repo = BatchRepository(db)

    chars = await char_repo.find_all(user_id=current_user)
    batches = await batch_repo.find_all(user_id=current_user)

    recent_batches = []
    char_map = {str(c["_id"]): c["name"] for c in chars}
    for b in batches[:10]:
        recent_batches.append({
            "batchId": str(b["_id"]),
            "batchName": b["batchName"],
            "characterName": char_map.get(b["characterId"], "Unknown"),
            "status": b["status"],
            "totalDays": b.get("totalDays", 0),
            "totalImages": b.get("totalImages", 0),
            "startDate": b.get("startDate", ""),
            "endDate": b.get("endDate", ""),
        })

    return {
        "totalCharacters": len(chars),
        "activeCharacters": sum(1 for c in chars if c.get("status") == "active"),
        "totalBatches": len(batches),
        "completedBatches": sum(1 for b in batches if b.get("status") == "COMPLETED"),
        "totalImages": sum(b.get("totalImages", 0) for b in batches),
        "recentBatches": recent_batches,
    }


@router.post("/test-ai")
async def test_ai():
    try:
        svc = GeminiService()
        result = await svc.ping()
        return {"success": True, **result}
    except Exception as e:
        return {"success": False, "error": str(e)[:300], "provider": "unknown", "latency_ms": 0}
