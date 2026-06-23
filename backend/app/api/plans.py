from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from app.schemas.content_plan import GeneratePlanRequest
from app.services.planning_service import PlanningService
from app.repositories.content_plan_repository import ContentPlanRepository
from app.repositories.image_prompt_repository import ImagePromptRepository

router = APIRouter(prefix="/plans", tags=["plans"])


@router.post("/generate", status_code=202)
async def generate_plan(body: GeneratePlanRequest, request: Request, background_tasks: BackgroundTasks):
    service = PlanningService(request.app.state.db)
    background_tasks.add_task(service.generate_plan, body.sessionId)
    return {"message": "Content plan generation started", "sessionId": body.sessionId}


@router.post("/generate/sync")
async def generate_plan_sync(body: GeneratePlanRequest, request: Request):
    service = PlanningService(request.app.state.db)
    try:
        result = await service.generate_plan(body.sessionId)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{session_id}")
async def get_plan(session_id: str, request: Request):
    repo = ContentPlanRepository(request.app.state.db)
    plans = await repo.find_by_session(session_id)
    return plans


@router.get("/{session_id}/prompts")
async def get_prompts(session_id: str, request: Request, status: str | None = None):
    repo = ImagePromptRepository(request.app.state.db)
    if status:
        prompts = await repo.find_by_session_and_status(session_id, status.upper())
    else:
        prompts = await repo.find_by_session(session_id)
    return prompts
