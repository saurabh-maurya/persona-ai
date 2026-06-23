from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel, Field


class ImageDescription(BaseModel):
    imageNo: int
    pose: str = ""
    bodyAngle: str = ""
    handPlacement: str = ""
    framing: str = ""


class DaySectionDB(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    batchId: str
    dayNo: int
    date: str  # ISO date string YYYY-MM-DD
    sectionName: str
    sectionOrder: int = 0
    contentType: str = ""
    sectionIntent: str = ""
    contentSummary: str = ""  # Gemini-generated 1-line summary of section content
    outfitFamily: str = ""
    lightingMood: str = ""
    cameraStyle: str = ""
    backgroundLocation: str = ""
    hashtags: list[str] = Field(default_factory=list)
    imageDescriptions: list[dict] = Field(default_factory=list)
    createdAt: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}
