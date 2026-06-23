from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.repositories.character_repository import CharacterRepository
from app.schemas.character import CharacterCreate, CharacterUpdate
from app.models.character import CharacterDB
from app.logging_config import get_logger

logger = get_logger(__name__)


async def generate_character_with_ai(name: str, niche: str, vibe: str, location: str) -> dict:
    from app.services.gemini_service import GeminiService
    gemini = GeminiService()
    return await gemini.generate_character(name=name, niche=niche, vibe=vibe, location=location)


class CharacterService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.repo = CharacterRepository(db)

    async def create(self, data: CharacterCreate, user_id: str | None = None) -> dict:
        character = CharacterDB(**data.model_dump())
        doc = character.model_dump(by_alias=True)
        doc["_id"] = ObjectId(doc["_id"])
        if user_id:
            doc["userId"] = user_id
        await self.repo.collection.insert_one(doc)
        doc["_id"] = str(doc["_id"])
        logger.info("character_created", name=data.name, user_id=user_id)
        return doc

    async def get_all(self, user_id: str | None = None) -> list[dict]:
        return await self.repo.find_all(user_id=user_id)

    async def get_by_id(self, id: str) -> dict | None:
        return await self.repo.find_by_id(id)

    async def get_by_id_for_user(self, id: str, user_id: str) -> dict | None:
        return await self.repo.find_by_id_for_user(id, user_id)

    async def update(self, id: str, data: CharacterUpdate, user_id: str | None = None) -> dict | None:
        if user_id:
            existing = await self.repo.find_by_id_for_user(id, user_id)
            if not existing:
                return None
        update_data = {k: v for k, v in data.model_dump().items() if v is not None}
        if not update_data:
            return await self.get_by_id(id)
        await self.repo.update_one(id, {"$set": update_data})
        return await self.get_by_id(id)

    async def delete(self, id: str) -> bool:
        return await self.repo.delete_one(id)
