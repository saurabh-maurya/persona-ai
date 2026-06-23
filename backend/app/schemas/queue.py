from pydantic import BaseModel


class QueueStartRequest(BaseModel):
    sessionId: str


class QueueRetryRequest(BaseModel):
    sessionId: str | None = None
    promptId: str | None = None


class JobStatusResponse(BaseModel):
    promptId: str
    jobId: str
    status: str
    attempts: int


class QueueStatusResponse(BaseModel):
    sessionId: str
    queued: int
    processing: int
    completed: int
    failed: int
    retrying: int
    total: int
