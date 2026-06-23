from motor.motor_asyncio import AsyncIOMotorDatabase
from app.repositories.base import BaseRepository


class BatchRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "batches")

    async def find_by_character(self, character_id: str, user_id: str) -> list[dict]:
        cursor = self.collection.find({"characterId": character_id, "userId": user_id}).sort("createdAt", -1)
        docs = await cursor.to_list(length=None)
        for d in docs:
            d["_id"] = str(d["_id"])
        return docs

    async def find_all(self, user_id: str) -> list[dict]:
        cursor = self.collection.find({"userId": user_id}).sort("createdAt", -1)
        docs = await cursor.to_list(length=None)
        for d in docs:
            d["_id"] = str(d["_id"])
        return docs

    async def find_by_id_for_user(self, batch_id: str, user_id: str) -> dict | None:
        from bson import ObjectId
        doc = await self.collection.find_one({"_id": ObjectId(batch_id), "userId": user_id})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
