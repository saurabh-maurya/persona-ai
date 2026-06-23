from motor.motor_asyncio import AsyncIOMotorDatabase
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "users")

    async def find_by_username(self, username: str) -> dict | None:
        return await self.find_one({"username": username})

    async def find_by_email(self, email: str) -> dict | None:
        return await self.find_one({"email": email})
