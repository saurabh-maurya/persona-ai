from fastapi import APIRouter, HTTPException, Request, Depends
from app.schemas.character import CharacterCreate, CharacterUpdate, CharacterResponse
from app.schemas.batch import CharacterAIGenerate
from app.services.character_service import CharacterService, generate_character_with_ai
from app.repositories.batch_repository import BatchRepository
from app.repositories.day_section_repository import DaySectionRepository
from app.dependencies import require_auth

router = APIRouter(prefix="/characters", tags=["characters"])


def _service(request: Request) -> CharacterService:
    return CharacterService(request.app.state.db)


@router.post("", response_model=dict, status_code=201)
async def create_character(body: CharacterCreate, request: Request, current_user: str = Depends(require_auth)):
    return await _service(request).create(body, user_id=current_user)


@router.get("")
async def list_characters(request: Request, current_user: str = Depends(require_auth)):
    return await _service(request).get_all(user_id=current_user)


@router.get("/{id}")
async def get_character(id: str, request: Request):
    character = await _service(request).get_by_id(id)
    if not character:
        raise HTTPException(404, "Character not found")
    return character


@router.put("/{id}")
async def update_character(id: str, body: CharacterUpdate, request: Request):
    character = await _service(request).update(id, body)
    if not character:
        raise HTTPException(404, "Character not found")
    return character


@router.get("/{id}/suggest-sequel")
async def suggest_sequel_context(id: str, request: Request):
    """Return a pre-filled contentSummary hint based on the character's most recent completed batch."""
    batch_repo = BatchRepository(request.app.state.db)
    section_repo = DaySectionRepository(request.app.state.db)

    all_batches = await batch_repo.find_by_character(id)
    completed = [b for b in all_batches if b.get("status") == "COMPLETED"]
    if not completed:
        return {"suggestion": "", "lastBatchName": "", "lastBatchId": ""}

    last = completed[0]  # find_by_character sorts by createdAt desc
    sections = await section_repo.find_by_batch(last["_id"])

    if not sections:
        return {
            "suggestion": f"Sequel to '{last['batchName']}'",
            "lastBatchName": last["batchName"],
            "lastBatchId": last["_id"],
        }

    locations = list(dict.fromkeys(s["backgroundLocation"] for s in sections if s.get("backgroundLocation")))[:2]
    outfits = list(dict.fromkeys(s["outfitFamily"] for s in sections if s.get("outfitFamily")))[:2]

    parts = []
    if locations:
        parts.append(f"visited {', '.join(locations)}")
    if outfits:
        parts.append(f"wore {', '.join(outfits)}")

    hint = f"Sequel to '{last['batchName']}' ({last['startDate']} → {last['endDate']})"
    if parts:
        hint += f" — character {' and '.join(parts)}. Continue the story naturally."

    return {"suggestion": hint, "lastBatchName": last["batchName"], "lastBatchId": last["_id"]}


@router.get("/{id}/batch-count")
async def get_character_batch_count(id: str, request: Request):
    """Return how many batches exist for this character (used by delete confirmation UI)."""
    batches = await BatchRepository(request.app.state.db).find_by_character(id)
    return {"characterId": id, "batchCount": len(batches)}


@router.delete("/{id}", status_code=204)
async def delete_character(id: str, request: Request):
    # Cascade: delete all batches and their day sections first
    batch_repo = BatchRepository(request.app.state.db)
    section_repo = DaySectionRepository(request.app.state.db)
    batches = await batch_repo.find_by_character(id)
    for batch in batches:
        await section_repo.delete_by_batch(batch["_id"])
    await request.app.state.db.batches.delete_many({"characterId": id})
    deleted = await _service(request).delete(id)
    if not deleted:
        raise HTTPException(404, "Character not found")


@router.post("/generate-ai")
async def ai_generate_character(body: CharacterAIGenerate):
    """Use Gemini to generate a full character profile from minimal input. Does not save to DB."""
    try:
        result = await generate_character_with_ai(
            name=body.name, niche=body.niche, vibe=body.vibe, location=body.location
        )
        return result
    except Exception as e:
        raise HTTPException(500, f"AI generation failed: {str(e)}")
