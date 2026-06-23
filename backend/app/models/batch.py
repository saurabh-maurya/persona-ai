from datetime import datetime
from enum import Enum
from bson import ObjectId
from pydantic import BaseModel, Field


class BatchStatus(str, Enum):
    CREATED = "CREATED"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class BatchDB(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    characterId: str
    batchName: str
    startDate: str  # ISO date string YYYY-MM-DD
    endDate: str    # ISO date string YYYY-MM-DD
    sections: list[dict] = Field(default_factory=list)  # [{name, imageCount}]
    contentSummary: str = ""  # user-provided context/sequel note
    status: BatchStatus = BatchStatus.CREATED
    totalDays: int = 0
    totalSections: int = 0
    totalImages: int = 0
    generatedSections: int = 0
    errorMessage: str = ""
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}
