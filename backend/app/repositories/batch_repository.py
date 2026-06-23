from motor.motor_asyncio import AsyncIOMotorDatabase
from app.repositories.base import BaseRepository


class BatchRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "batches")

    async def find_by_character(self, character_id: str) -> list[dict]:
        cursor = self.collection.find({"characterId": character_id}).sort("createdAt", -1)
        docs = await cursor.to_list(length=None)
        for d in docs:
            d["_id"] = str(d["_id"])
        return docs

    async def find_all(self, user_id: str | None = None) -> list[dict]:
        query = {"$or": [{"userId": user_id}, {"userId": {"$exists": False}}]} if user_id else {}
        cursor = self.collection.find(query).sort("createdAt", -1)
        docs = await cursor.to_list(length=None)
        for d in docs:
            d["_id"] = str(d["_id"])
        return docs
