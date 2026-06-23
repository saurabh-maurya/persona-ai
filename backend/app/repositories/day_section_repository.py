from motor.motor_asyncio import AsyncIOMotorDatabase
from app.repositories.base import BaseRepository


class DaySectionRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "daySections")

    async def find_by_batch(self, batch_id: str) -> list[dict]:
        cursor = self.collection.find({"batchId": batch_id}).sort([("dayNo", 1), ("sectionOrder", 1), ("sectionName", 1)])
        docs = await cursor.to_list(length=None)
        for d in docs:
            d["_id"] = str(d["_id"])
        return docs

    async def find_by_batch_and_day(self, batch_id: str, day_no: int) -> list[dict]:
        cursor = self.collection.find({"batchId": batch_id, "dayNo": day_no}).sort([("sectionOrder", 1), ("sectionName", 1)])
        docs = await cursor.to_list(length=None)
        for d in docs:
            d["_id"] = str(d["_id"])
        return docs

    async def delete_by_batch(self, batch_id: str) -> None:
        await self.collection.delete_many({"batchId": batch_id})

    async def get_recent_summaries(self, character_id: str, limit: int = 3) -> list[str]:
        """Get contentSummary strings from the most recent completed batches for context."""
        from bson import ObjectId
        # Find recent completed batch IDs for this character
        batches_cursor = self.collection.database["batches"].find(
            {"characterId": character_id, "status": "COMPLETED"},
            sort=[("createdAt", -1)],
            limit=limit,
        )
        recent_batches = await batches_cursor.to_list(length=None)
        batch_ids = [str(b["_id"]) for b in recent_batches]
        if not batch_ids:
            return []

        cursor = self.collection.find(
            {"batchId": {"$in": batch_ids}},
            sort=[("createdAt", -1)],
        )
        docs = await cursor.to_list(length=None)
        summaries = [d["contentSummary"] for d in docs if d.get("contentSummary")]
        return summaries
