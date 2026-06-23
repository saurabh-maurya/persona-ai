from motor.motor_asyncio import AsyncIOMotorDatabase
from app.repositories.base import BaseRepository


class CharacterRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "characters")

    async def find_active(self) -> list[dict]:
        return await self.find_many({"status": "active"})

    async def find_all(self, user_id: str | None = None) -> list[dict]:
        query = {"$or": [{"userId": user_id}, {"userId": {"$exists": False}}]} if user_id else {}
        return await self.find_many(query, sort=[("createdAt", -1)])

    async def find_by_name(self, name: str) -> dict | None:
        return await self.find_one({"name": name})
