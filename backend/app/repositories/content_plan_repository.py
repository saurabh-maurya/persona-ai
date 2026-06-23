from motor.motor_asyncio import AsyncIOMotorDatabase
from app.repositories.base import BaseRepository


class ContentPlanRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "contentPlans")

    async def find_by_session(self, session_id: str) -> list[dict]:
        return await self.find_many(
            {"sessionId": session_id},
            sort=[("dayNo", 1), ("section", 1)]
        )

    async def find_by_session_and_day(self, session_id: str, day_no: int) -> list[dict]:
        return await self.find_many(
            {"sessionId": session_id, "dayNo": day_no},
            sort=[("section", 1)]
        )

    async def delete_by_session(self, session_id: str) -> int:
        result = await self.collection.delete_many({"sessionId": session_id})
        return result.deleted_count
