from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks, Depends
from bson import ObjectId
from app.schemas.batch import BatchCreate, BatchUpdate
from app.services.generation_service import GenerationService
from app.repositories.batch_repository import BatchRepository
from app.repositories.day_section_repository import DaySectionRepository
from app.repositories.character_repository import CharacterRepository
from app.models.batch import BatchDB, BatchStatus
from app.dependencies import require_auth

router = APIRouter(prefix="/batches", tags=["batches"])


def _batch_repo(request: Request) -> BatchRepository:
    return BatchRepository(request.app.state.db)


def _section_repo(request: Request) -> DaySectionRepository:
    return DaySectionRepository(request.app.state.db)


async def _get_owned_batch(repo: BatchRepository, batch_id: str, user_id: str) -> dict:
    batch = await repo.find_by_id_for_user(batch_id, user_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    return batch


@router.get("")
async def list_batches(request: Request, character_id: str | None = None, current_user: str = Depends(require_auth)):
    repo = _batch_repo(request)
    if character_id:
        batches = await repo.find_by_character(character_id, user_id=current_user)
    else:
        batches = await repo.find_all(user_id=current_user)

    char_repo = CharacterRepository(request.app.state.db)
    char_cache: dict[str, str] = {}
    for b in batches:
        cid = b.get("characterId", "")
        if cid not in char_cache:
            char = await char_repo.find_by_id(cid)
            char_cache[cid] = char["name"] if char else "Unknown"
        b["characterName"] = char_cache[cid]
    return batches


@router.post("", status_code=201)
async def create_batch(body: BatchCreate, request: Request, current_user: str = Depends(require_auth)):
    from datetime import datetime as dt
    start = dt.strptime(body.startDate, "%Y-%m-%d")
    end = dt.strptime(body.endDate, "%Y-%m-%d")
    if end < start:
        raise HTTPException(400, "endDate must be >= startDate")

    num_days = (end - start).days + 1
    total_sections = num_days * len(body.sections)
    total_images = num_days * sum(s.imageCount for s in body.sections)

    batch = BatchDB(
        characterId=body.characterId,
        batchName=body.batchName,
        startDate=body.startDate,
        endDate=body.endDate,
        sections=[s.model_dump() for s in body.sections],
        contentSummary=body.contentSummary,
        totalDays=num_days,
        totalSections=total_sections,
        totalImages=total_images,
    )
    doc = batch.model_dump(by_alias=True)
    doc["_id"] = ObjectId(doc["_id"])
    doc["userId"] = current_user
    await request.app.state.db.batches.insert_one(doc)
    doc["_id"] = str(doc["_id"])
    return doc


@router.get("/{batch_id}")
async def get_batch(batch_id: str, request: Request, current_user: str = Depends(require_auth)):
    batch = await _get_owned_batch(_batch_repo(request), batch_id, current_user)
    char = await CharacterRepository(request.app.state.db).find_by_id(batch["characterId"])
    batch["characterName"] = char["name"] if char else "Unknown"
    return batch


@router.put("/{batch_id}")
async def update_batch(batch_id: str, body: BatchUpdate, request: Request, current_user: str = Depends(require_auth)):
    repo = _batch_repo(request)
    await _get_owned_batch(repo, batch_id, current_user)
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_data:
        return await repo.find_by_id_for_user(batch_id, current_user)
    update_data["updatedAt"] = datetime.utcnow()
    await repo.update_one(batch_id, {"$set": update_data})
    return await repo.find_by_id_for_user(batch_id, current_user)


@router.delete("/{batch_id}", status_code=204)
async def delete_batch(batch_id: str, request: Request, current_user: str = Depends(require_auth)):
    await _get_owned_batch(_batch_repo(request), batch_id, current_user)
    await _section_repo(request).delete_by_batch(batch_id)
    await _batch_repo(request).delete_one(batch_id)


@router.post("/{batch_id}/duplicate", status_code=201)
async def duplicate_batch(batch_id: str, request: Request, current_user: str = Depends(require_auth)):
    original = await _get_owned_batch(_batch_repo(request), batch_id, current_user)

    from datetime import datetime as dt
    start_str = original["startDate"]
    end_str = original["endDate"]
    start = dt.strptime(start_str, "%Y-%m-%d")
    end = dt.strptime(end_str, "%Y-%m-%d")
    num_days = (end - start).days + 1
    sections = original.get("sections", [])

    new_batch = BatchDB(
        characterId=original["characterId"],
        batchName=f"{original['batchName']} (copy)",
        startDate=start_str,
        endDate=end_str,
        sections=sections,
        contentSummary=original.get("contentSummary", ""),
        totalDays=num_days,
        totalSections=num_days * len(sections),
        totalImages=num_days * sum(s.get("imageCount", 0) for s in sections),
    )
    doc = new_batch.model_dump(by_alias=True)
    doc["_id"] = ObjectId(doc["_id"])
    doc["userId"] = current_user
    await request.app.state.db.batches.insert_one(doc)
    doc["_id"] = str(doc["_id"])
    return doc


@router.post("/{batch_id}/generate", status_code=202)
async def generate_batch(batch_id: str, request: Request, background_tasks: BackgroundTasks, current_user: str = Depends(require_auth)):
    batch = await _get_owned_batch(_batch_repo(request), batch_id, current_user)
    if batch["status"] == BatchStatus.GENERATING:
        raise HTTPException(409, "Generation already in progress")

    service = GenerationService(request.app.state.db)
    background_tasks.add_task(service.generate_batch, batch_id)
    return {"message": "Generation started", "batchId": batch_id}


@router.post("/{batch_id}/generate/sync")
async def generate_batch_sync(batch_id: str, request: Request, current_user: str = Depends(require_auth)):
    await _get_owned_batch(_batch_repo(request), batch_id, current_user)
    service = GenerationService(request.app.state.db)
    try:
        result = await service.generate_batch(batch_id)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{batch_id}/days")
async def get_batch_days(batch_id: str, request: Request, current_user: str = Depends(require_auth)):
    await _get_owned_batch(_batch_repo(request), batch_id, current_user)
    sections = await _section_repo(request).find_by_batch(batch_id)
    days: dict[int, dict] = {}
    for sec in sections:
        day_no = sec["dayNo"]
        if day_no not in days:
            days[day_no] = {"dayNo": day_no, "date": sec["date"], "sections": []}
        days[day_no]["sections"].append(sec)
    return [days[k] for k in sorted(days.keys())]


@router.get("/{batch_id}/days/{day_no}")
async def get_batch_day(batch_id: str, day_no: int, request: Request, current_user: str = Depends(require_auth)):
    await _get_owned_batch(_batch_repo(request), batch_id, current_user)
    sections = await _section_repo(request).find_by_batch_and_day(batch_id, day_no)
    if not sections:
        raise HTTPException(404, "Day not found")
    return {"dayNo": day_no, "date": sections[0]["date"], "sections": sections}


@router.post("/{batch_id}/days/{day_no}/sections/{section_name}/generate")
async def regenerate_section(batch_id: str, day_no: int, section_name: str, request: Request, current_user: str = Depends(require_auth)):
    await _get_owned_batch(_batch_repo(request), batch_id, current_user)
    service = GenerationService(request.app.state.db)
    try:
        result = await service.regenerate_section(batch_id, day_no, section_name)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
