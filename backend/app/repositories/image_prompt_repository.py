from motor.motor_asyncio import AsyncIOMotorDatabase
from app.repositories.base import BaseRepository
from app.models.image_prompt import PromptStatus


class ImagePromptRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "imagePrompts")

    async def find_by_session(self, session_id: str) -> list[dict]:
        return await self.find_many(
            {"sessionId": session_id},
            sort=[("dayNo", 1), ("imageNo", 1)]
        )

    async def find_by_session_and_status(self, session_id: str, status: str) -> list[dict]:
        return await self.find_many({"sessionId": session_id, "status": status})

    async def find_failed(self, session_id: str) -> list[dict]:
        return await self.find_many(
            {"sessionId": session_id, "status": PromptStatus.FAILED}
        )

    async def find_pending(self, session_id: str) -> list[dict]:
        return await self.find_many(
            {"sessionId": session_id, "status": PromptStatus.QUEUED}
        )

    async def count_by_status(self, session_id: str) -> dict:
        pipeline = [
            {"$match": {"sessionId": session_id}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]
        results = await self.collection.aggregate(pipeline).to_list(length=None)
        return {r["_id"]: r["count"] for r in results}

    async def count_all_by_status(self) -> dict:
        pipeline = [
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]
        results = await self.collection.aggregate(pipeline).to_list(length=None)
        return {r["_id"]: r["count"] for r in results}

    async def delete_by_session(self, session_id: str) -> int:
        result = await self.collection.delete_many({"sessionId": session_id})
        return result.deleted_count
