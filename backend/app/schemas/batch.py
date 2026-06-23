from datetime import datetime
from pydantic import BaseModel, Field
from app.models.batch import BatchStatus


class SectionConfig(BaseModel):
    name: str
    imageCount: int = Field(..., ge=1, le=50)


class BatchCreate(BaseModel):
    characterId: str
    batchName: str = Field(..., min_length=1)
    startDate: str  # YYYY-MM-DD
    endDate: str    # YYYY-MM-DD
    sections: list[SectionConfig] = Field(..., min_length=1)
    contentSummary: str = ""


class BatchUpdate(BaseModel):
    batchName: str | None = None
    contentSummary: str | None = None
    status: BatchStatus | None = None


class CharacterAIGenerate(BaseModel):
    name: str = Field(..., min_length=1)
    niche: str = Field(..., min_length=1)
    vibe: str = Field(..., min_length=1)
    location: str = Field(..., min_length=1)
