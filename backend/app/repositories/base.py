from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


def _to_str_id(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


class BaseRepository:
    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str):
        self.collection = db[collection_name]

    async def find_by_id(self, id: str) -> dict | None:
        doc = await self.collection.find_one({"_id": ObjectId(id)})
        return _to_str_id(doc) if doc else None

    async def find_one(self, filter: dict) -> dict | None:
        doc = await self.collection.find_one(filter)
        return _to_str_id(doc) if doc else None

    async def find_many(self, filter: dict, limit: int = 0, skip: int = 0, sort: list | None = None) -> list[dict]:
        cursor = self.collection.find(filter)
        if sort:
            cursor = cursor.sort(sort)
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        docs = await cursor.to_list(length=None)
        return [_to_str_id(d) for d in docs]

    async def insert_one(self, data: dict) -> str:
        if "_id" in data and isinstance(data["_id"], str):
            data["_id"] = ObjectId(data["_id"])
        result = await self.collection.insert_one(data)
        return str(result.inserted_id)

    async def update_one(self, id: str, update: dict) -> bool:
        update.setdefault("$set", {})["updatedAt"] = datetime.utcnow()
        result = await self.collection.update_one(
            {"_id": ObjectId(id)}, update
        )
        return result.modified_count > 0

    async def delete_one(self, id: str) -> bool:
        result = await self.collection.delete_one({"_id": ObjectId(id)})
        return result.deleted_count > 0

    async def count(self, filter: dict) -> int:
        return await self.collection.count_documents(filter)
