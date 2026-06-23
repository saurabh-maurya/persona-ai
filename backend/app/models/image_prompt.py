from datetime import datetime
from enum import Enum
from bson import ObjectId
from pydantic import BaseModel, Field


class PromptStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"


class ImagePromptDB(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    sessionId: str
    contentPlanId: str
    dayNo: int
    section: str
    imageNo: int
    prompt: str
    status: PromptStatus = PromptStatus.QUEUED
    jobId: str = ""
    attempts: int = 0
    errorMessage: str = ""
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}
