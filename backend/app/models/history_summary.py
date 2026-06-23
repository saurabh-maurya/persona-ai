from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel, Field


class HistorySummaryDB(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    characterId: str
    summary: str
    recentOutfits: list[str] = Field(default_factory=list)
    recentLocations: list[str] = Field(default_factory=list)
    recentThemes: list[str] = Field(default_factory=list)
    recentCameraAngles: list[str] = Field(default_factory=list)
    recentMoods: list[str] = Field(default_factory=list)
    promptCount: int = 0
    generatedAt: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}
