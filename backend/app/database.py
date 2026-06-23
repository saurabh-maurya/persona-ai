import certifi
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import get_settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncIOMotorClient(settings.mongodb_url, tlsCAFile=certifi.where())
    return _client


def get_db() -> AsyncIOMotorDatabase:
    settings = get_settings()
    return get_client()[settings.mongodb_db]


async def close_db() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


async def init_indexes() -> None:
    db = get_db()
    await db.users.create_index("username", unique=True)
    await db.users.create_index("email", unique=True)
    await db.characters.create_index("name")
    await db.characters.create_index("status")
    await db.characters.create_index("userId")
    await db.batches.create_index("characterId")
    await db.batches.create_index("status")
    await db.batches.create_index("userId")
    await db.daySections.create_index([("batchId", 1), ("dayNo", 1)])
    await db.daySections.create_index("batchId")
