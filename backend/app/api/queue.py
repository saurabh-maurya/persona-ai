from fastapi import APIRouter, HTTPException, Request
from app.schemas.queue import QueueStartRequest, QueueRetryRequest, QueueStatusResponse
from app.services.queue_service import QueueService

router = APIRouter(prefix="/queue", tags=["queue"])


def _service(request: Request) -> QueueService:
    return QueueService(request.app.state.db)


@router.post("/start")
async def start_queue(body: QueueStartRequest, request: Request):
    service = _service(request)
    try:
        count = await service.enqueue_session(body.sessionId)
        return {"message": f"Enqueued {count} jobs", "sessionId": body.sessionId, "jobsQueued": count}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/retry")
async def retry_failed(body: QueueRetryRequest, request: Request):
    service = _service(request)
    count = await service.retry_failed(
        session_id=body.sessionId,
        prompt_id=body.promptId
    )
    return {"message": f"Retried {count} jobs", "retried": count}


@router.get("/status/{session_id}", response_model=QueueStatusResponse)
async def queue_status(session_id: str, request: Request):
    service = _service(request)
    return await service.get_status(session_id)


@router.get("/status")
async def global_queue_status(request: Request):
    service = _service(request)
    return await service.get_global_status()
