import re
from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.repositories.content_plan_repository import ContentPlanRepository
from app.repositories.image_prompt_repository import ImagePromptRepository
from app.services.gemini_service import GeminiService
from app.logging_config import get_logger

logger = get_logger(__name__)


class HistoryService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.content_plan_repo = ContentPlanRepository(db)
        self.image_prompt_repo = ImagePromptRepository(db)
        self.gemini_service = GeminiService()

    async def get_history_summary(self, character_id: str) -> str:
        doc = await self.db.historySummary.find_one(
            {"characterId": character_id},
            sort=[("generatedAt", -1)]
        )
        if doc:
            return doc.get("summary", "")
        return ""

    async def generate_and_save_summary(self, character_id: str) -> str:
        sessions = await self.db.sessions.find({"characterId": character_id}).to_list(length=None)
        session_ids = [str(s["_id"]) for s in sessions]

        if not session_ids:
            return ""

        all_prompts = await self.db.imagePrompts.find(
            {"sessionId": {"$in": session_ids}, "status": "COMPLETED"}
        ).sort("createdAt", -1).limit(50).to_list(length=None)

        all_plans = await self.db.contentPlans.find(
            {"sessionId": {"$in": session_ids}}
        ).sort("createdAt", -1).limit(50).to_list(length=None)

        outfits, locations, camera_angles, moods = [], [], [], []
        themes = []

        for plan in all_plans:
            shared = plan.get("sharedDescription", {})
            if shared.get("outfitFamily"):
                outfits.append(shared["outfitFamily"])
            if shared.get("backgroundLocation"):
                locations.append(shared["backgroundLocation"])
            if shared.get("cameraStyle"):
                camera_angles.append(shared["cameraStyle"])
            if shared.get("lightingMood"):
                moods.append(shared["lightingMood"])
            if plan.get("sectionIntent"):
                themes.append(plan["sectionIntent"])

        prompts_text = [p.get("prompt", "") for p in all_prompts]

        summary = await self.gemini_service.summarize_history(
            prompts=prompts_text,
            outfits=outfits,
            themes=themes,
            locations=locations,
            camera_angles=camera_angles,
            moods=moods
        )

        doc = {
            "_id": ObjectId(),
            "characterId": character_id,
            "summary": summary,
            "recentOutfits": outfits[-50:],
            "recentLocations": locations[-50:],
            "recentThemes": themes[-50:],
            "recentCameraAngles": camera_angles[-50:],
            "recentMoods": moods[-50:],
            "promptCount": len(prompts_text),
            "generatedAt": datetime.utcnow()
        }
        await self.db.historySummary.insert_one(doc)
        logger.info("history_summary_saved", character_id=character_id)
        return summary
