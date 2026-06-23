from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel, Field


class ContentPlanDB(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    sessionId: str
    dayNo: int
    section: str
    contentType: str
    sectionIntent: str
    sharedDescription: dict = Field(default_factory=dict)
    hashtags: list[str] = Field(default_factory=list)
    imageCount: int = 0
    createdAt: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}
