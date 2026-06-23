from motor.motor_asyncio import AsyncIOMotorDatabase
from app.repositories.base import BaseRepository


class CharacterRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "characters")

    async def find_active(self, user_id: str) -> list[dict]:
        return await self.find_many({"status": "active", "userId": user_id})

    async def find_all(self, user_id: str) -> list[dict]:
        return await self.find_many({"userId": user_id}, sort=[("createdAt", -1)])

    async def find_by_id_for_user(self, id: str, user_id: str) -> dict | None:
        from bson import ObjectId
        doc = await self.collection.find_one({"_id": ObjectId(id), "userId": user_id})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
