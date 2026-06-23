from datetime import datetime, date
from enum import Enum
from bson import ObjectId
from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    PLANNED = "PLANNED"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SessionDB(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    characterId: str
    sessionName: str
    startDate: str
    endDate: str
    contentStructure: dict = Field(default_factory=dict)
    status: SessionStatus = SessionStatus.CREATED
    totalDays: int = 0
    totalImages: int = 0
    generatedImages: int = 0
    failedImages: int = 0
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}
