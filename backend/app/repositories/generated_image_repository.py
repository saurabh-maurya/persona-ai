from motor.motor_asyncio import AsyncIOMotorDatabase
from app.repositories.base import BaseRepository


class GeneratedImageRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "generatedImages")

    async def find_by_session(self, session_id: str) -> list[dict]:
        return await self.find_many(
            {"sessionId": session_id},
            sort=[("createdAt", -1)]
        )

    async def find_by_prompt(self, prompt_id: str) -> dict | None:
        return await self.find_one({"imagePromptId": prompt_id})

    async def count_by_character(self, character_id: str) -> int:
        return await self.count({"characterId": character_id})

    async def count_total(self) -> int:
        return await self.count({})
