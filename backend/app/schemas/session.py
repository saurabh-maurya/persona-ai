from datetime import datetime
from pydantic import BaseModel, Field
from app.models.session import SessionStatus


class ContentStructureInput(BaseModel):
    sections: dict[str, int] = Field(
        ...,
        description="Section name to image count, e.g. {'Morning': 3, 'Evening': 5, 'Night': 10}",
        examples=[{"Morning": 3, "Evening": 5, "Night": 10}]
    )


class SessionCreate(BaseModel):
    characterId: str
    startDate: str = Field(..., description="YYYY-MM-DD")
    endDate: str = Field(..., description="YYYY-MM-DD")
    contentStructure: ContentStructureInput


class SessionResponse(BaseModel):
    id: str
    characterId: str
    sessionName: str
    startDate: str
    endDate: str
    contentStructure: dict
    status: SessionStatus
    totalDays: int
    totalImages: int
    generatedImages: int
    failedImages: int
    completionPct: float = 0.0
    createdAt: datetime
    updatedAt: datetime
