from datetime import datetime
from pydantic import BaseModel, Field
from app.models.character import CharacterStatus


class CharacterCreate(BaseModel):
    name: str = Field(..., min_length=1)
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


class CharacterUpdate(BaseModel):
    name: str | None = None
    age: str | None = None
    gender: str | None = None
    persona: str | None = None
    appearance: str | None = None
    fashionStyle: str | None = None
    audience: str | None = None
    niche: str | None = None
    city: str | None = None
    country: str | None = None
    masterPrompt: str | None = None
    status: CharacterStatus | None = None


class CharacterResponse(BaseModel):
    id: str
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
    masterPrompt: str
    status: CharacterStatus
    createdAt: datetime
    updatedAt: datetime
