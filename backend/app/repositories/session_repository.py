from motor.motor_asyncio import AsyncIOMotorDatabase
from app.repositories.base import BaseRepository


class SessionRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "sessions")

    async def find_by_character(self, character_id: str) -> list[dict]:
        return await self.find_many({"characterId": character_id}, sort=[("createdAt", -1)])

    async def find_all(self, limit: int = 50) -> list[dict]:
        return await self.find_many({}, limit=limit, sort=[("createdAt", -1)])

    async def find_by_status(self, status: str) -> list[dict]:
        return await self.find_many({"status": status})

    async def find_by_session_name(self, name: str) -> dict | None:
        return await self.find_one({"sessionName": name})

    async def increment_generated(self, session_id: str) -> None:
        from bson import ObjectId
        await self.collection.update_one(
            {"_id": ObjectId(session_id)},
            {"$inc": {"generatedImages": 1}}
        )

    async def increment_failed(self, session_id: str) -> None:
        from bson import ObjectId
        await self.collection.update_one(
            {"_id": ObjectId(session_id)},
            {"$inc": {"failedImages": 1}}
        )
