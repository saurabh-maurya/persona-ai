from datetime import datetime
from enum import Enum
from bson import ObjectId
from pydantic import BaseModel, Field


class CharacterStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class CharacterDB(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    name: str
    age: str
    gender: str
    persona: str
    appearance: str
    fashionStyle: str
    audience: str
    niche: str
    city: str
    country: str
    masterPrompt: str = ""
    status: CharacterStatus = CharacterStatus.ACTIVE
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}
