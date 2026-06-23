from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel, Field


class GeneratedImageDB(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    imagePromptId: str
    sessionId: str
    characterId: str
    driveFileId: str = ""
    driveUrl: str = ""
    localPath: str = ""
    generationTime: float = 0.0
    status: str = "completed"
    createdAt: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}
