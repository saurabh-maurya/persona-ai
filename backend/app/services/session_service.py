from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.repositories.character_repository import CharacterRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.session import SessionCreate
from app.models.session import SessionDB, SessionStatus
from app.logging_config import get_logger

logger = get_logger(__name__)


def _session_name(character_name: str, start_date: str, count: int) -> str:
    slug = character_name.replace(" ", "_")
    date_slug = start_date.replace("-", "_")
    return f"{slug}_{date_slug}_{count:03d}"


class SessionService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.repo = SessionRepository(db)
        self.char_repo = CharacterRepository(db)

    async def create(self, data: SessionCreate) -> dict:
        character = await self.char_repo.find_by_id(data.characterId)
        if not character:
            raise ValueError(f"Character {data.characterId} not found")

        existing_count = await self.repo.count({"characterId": data.characterId})
        session_name = _session_name(character["name"], data.startDate, existing_count + 1)

        start = datetime.strptime(data.startDate, "%Y-%m-%d")
        end = datetime.strptime(data.endDate, "%Y-%m-%d")
        total_days = (end - start).days + 1

        sections = data.contentStructure.sections
        images_per_day = sum(sections.values())
        total_images_estimate = total_days * images_per_day

        session = {
            "_id": ObjectId(),
            "characterId": data.characterId,
            "sessionName": session_name,
            "startDate": data.startDate,
            "endDate": data.endDate,
            "contentStructure": {"sections": sections},
            "status": SessionStatus.CREATED,
            "totalDays": total_days,
            "totalImages": total_images_estimate,
            "generatedImages": 0,
            "failedImages": 0,
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow(),
        }

        await self.db.sessions.insert_one(session)
        session["_id"] = str(session["_id"])
        logger.info("session_created", session_name=session_name)
        return session

    async def get_all(self, limit: int = 50) -> list[dict]:
        return await self.repo.find_all(limit=limit)

    async def get_by_id(self, id: str) -> dict | None:
        session = await self.repo.find_by_id(id)
        if session:
            total = session.get("totalImages", 0)
            generated = session.get("generatedImages", 0)
            session["completionPct"] = round((generated / total * 100) if total > 0 else 0, 1)
        return session

    async def get_by_character(self, character_id: str) -> list[dict]:
        return await self.repo.find_by_character(character_id)

    async def delete(self, id: str) -> bool:
        session = await self.repo.find_by_id(id)
        if not session:
            return False
        # Delete all related data
        await self.db.contentPlans.delete_many({"sessionId": id})
        await self.db.imagePrompts.delete_many({"sessionId": id})
        await self.db.generatedImages.delete_many({"sessionId": id})
        await self.repo.delete_one(id)
        logger.info("session_deleted", session_id=id)
        return True
