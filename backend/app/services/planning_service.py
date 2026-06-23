import re
from datetime import datetime, timedelta
from pathlib import Path
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.repositories.character_repository import CharacterRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.content_plan_repository import ContentPlanRepository
from app.repositories.image_prompt_repository import ImagePromptRepository
from app.services.gemini_service import GeminiService
from app.services.history_service import HistoryService
from app.models.session import SessionStatus
from app.logging_config import get_logger

logger = get_logger(__name__)

_MASTER_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "master_image_description.md"


def _load_master_prompt() -> str:
    if _MASTER_PROMPT_PATH.exists():
        return _MASTER_PROMPT_PATH.read_text()
    return ""


def _parse_content_plan(raw_text: str, session_id: str) -> list[dict]:
    """Parse Gemini output into structured content plan documents."""
    plans = []
    current_day = None
    current_section = None
    current_plan = None
    current_images = []
    current_image = None

    lines = raw_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Day marker
        day_match = re.match(r"^Day\s+(\d+)\s*[:\-]?\s*$", line, re.IGNORECASE)
        if day_match:
            if current_plan and current_section:
                if current_image:
                    current_images.append(current_image)
                    current_image = None
                current_plan["images"] = current_images
                plans.append(current_plan)
                current_images = []
            current_day = int(day_match.group(1))
            current_section = None
            current_plan = None
            i += 1
            continue

        # Section header (Morning:, Evening:, Night:, etc.)
        section_match = re.match(r"^([A-Za-z][A-Za-z\s]+?)\s*[:\-]\s*$", line)
        if section_match and current_day and line not in ("Content Type:", "Shared Description:"):
            section_name = section_match.group(1).strip()
            if len(section_name.split()) <= 3 and not any(
                kw in section_name.lower() for kw in ["content type", "section intent", "shared description", "hashtag", "image"]
            ):
                if current_plan and current_section:
                    if current_image:
                        current_images.append(current_image)
                        current_image = None
                    current_plan["images"] = current_images
                    plans.append(current_plan)
                    current_images = []

                current_section = section_name
                current_plan = {
                    "sessionId": session_id,
                    "dayNo": current_day,
                    "section": section_name,
                    "contentType": "",
                    "sectionIntent": "",
                    "sharedDescription": {},
                    "hashtags": [],
                    "images": []
                }
                i += 1
                continue

        if not current_plan:
            i += 1
            continue

        # Content Type
        ct_match = re.match(r"^Content\s+Type\s*[:\-]\s*(.+)$", line, re.IGNORECASE)
        if ct_match:
            current_plan["contentType"] = ct_match.group(1).strip()
            i += 1
            continue

        # Section Intent
        si_match = re.match(r"^Section\s+Intent\s*[:\-]\s*(.+)$", line, re.IGNORECASE)
        if si_match:
            current_plan["sectionIntent"] = si_match.group(1).strip()
            i += 1
            continue

        # Shared Description block
        if re.match(r"^Shared\s+Description\s*[:\-]?$", line, re.IGNORECASE):
            i += 1
            while i < len(lines):
                sub = lines[i].strip()
                if not sub or re.match(r"^Hashtags\s*[:\-]?$", sub, re.IGNORECASE) or re.match(r"^Image\s+\d+", sub, re.IGNORECASE):
                    break
                for field, key in [("Outfit family", "outfitFamily"), ("Lighting mood", "lightingMood"),
                                    ("Camera style", "cameraStyle"), ("Background location", "backgroundLocation")]:
                    m = re.match(rf"^[-\*]?\s*{field}\s*[:\-]\s*(.+)$", sub, re.IGNORECASE)
                    if m:
                        current_plan["sharedDescription"][key] = m.group(1).strip()
                i += 1
            continue

        # Hashtags
        if re.match(r"^Hashtags\s*[:\-]?$", line, re.IGNORECASE):
            i += 1
            while i < len(lines):
                sub = lines[i].strip()
                if not sub:
                    i += 1
                    break
                if sub.startswith("#") or re.search(r"#\w+", sub):
                    tags = re.findall(r"#\w+", sub)
                    current_plan["hashtags"].extend(tags)
                    i += 1
                else:
                    break
            continue

        # Image N:
        img_match = re.match(r"^Image\s+(\d+)\s*[:\-]?\s*$", line, re.IGNORECASE)
        if img_match:
            if current_image:
                current_images.append(current_image)
            current_image = {
                "imageNo": int(img_match.group(1)),
                "pose": "",
                "bodyAngle": "",
                "handPlacement": "",
                "framing": "",
            }
            i += 1
            continue

        # Image fields
        if current_image:
            for field, key in [("Pose", "pose"), ("Body angle", "bodyAngle"),
                                ("Hand placement", "handPlacement"), ("Framing", "framing")]:
                m = re.match(rf"^[-\*]?\s*{field}\s*[:\-]\s*(.+)$", line, re.IGNORECASE)
                if m:
                    current_image[key] = m.group(1).strip()

        i += 1

    # Flush last plan
    if current_plan and current_section:
        if current_image:
            current_images.append(current_image)
        current_plan["images"] = current_images
        plans.append(current_plan)

    return plans


def _build_full_prompt(plan: dict, image: dict) -> str:
    shared = plan.get("sharedDescription", {})
    parts = []
    if plan.get("sectionIntent"):
        parts.append(plan["sectionIntent"])
    if shared.get("outfitFamily"):
        parts.append(f"Outfit: {shared['outfitFamily']}")
    if shared.get("lightingMood"):
        parts.append(f"Lighting: {shared['lightingMood']}")
    if shared.get("cameraStyle"):
        parts.append(f"Camera: {shared['cameraStyle']}")
    if shared.get("backgroundLocation"):
        parts.append(f"Location: {shared['backgroundLocation']}")
    if image.get("pose"):
        parts.append(f"Pose: {image['pose']}")
    if image.get("bodyAngle"):
        parts.append(f"Body angle: {image['bodyAngle']}")
    if image.get("handPlacement"):
        parts.append(f"Hand placement: {image['handPlacement']}")
    if image.get("framing"):
        parts.append(f"Framing: {image['framing']}")
    return ". ".join(parts)


class PlanningService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.character_repo = CharacterRepository(db)
        self.session_repo = SessionRepository(db)
        self.content_plan_repo = ContentPlanRepository(db)
        self.image_prompt_repo = ImagePromptRepository(db)
        self.gemini_service = GeminiService()
        self.history_service = HistoryService(db)

    async def generate_plan(self, session_id: str) -> dict:
        try:
            return await self._generate_plan_inner(session_id)
        except Exception as exc:
            logger.error("plan_generation_failed", session_id=session_id, error=str(exc))
            await self.session_repo.update_one(
                session_id,
                {"$set": {"status": SessionStatus.FAILED, "errorMessage": str(exc)}},
            )
            raise

    async def _generate_plan_inner(self, session_id: str) -> dict:
        session = await self.session_repo.find_by_id(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        character = await self.character_repo.find_by_id(session["characterId"])
        if not character:
            raise ValueError(f"Character {session['characterId']} not found")

        await self.session_repo.update_one(session_id, {"$set": {"status": SessionStatus.PLANNING}})

        history_summary = await self.history_service.get_history_summary(session["characterId"])

        start = datetime.strptime(session["startDate"], "%Y-%m-%d")
        end = datetime.strptime(session["endDate"], "%Y-%m-%d")
        num_days = (end - start).days + 1

        content_structure = session.get("contentStructure", {})
        sections = content_structure.get("sections", {})

        master_prompt = _load_master_prompt()

        logger.info("generating_plan", session_id=session_id, days=num_days, sections=sections)

        raw_output = await self.gemini_service.generate_content_plan(
            character=character,
            num_days=num_days,
            content_structure=sections,
            history_summary=history_summary,
            master_prompt_template=master_prompt,
        )

        parsed_plans = _parse_content_plan(raw_output, session_id)

        await self.content_plan_repo.delete_by_session(session_id)
        await self.image_prompt_repo.delete_by_session(session_id)

        total_images = 0
        image_prompts = []

        for plan_data in parsed_plans:
            images = plan_data.pop("images", [])
            plan_data["imageCount"] = len(images)
            plan_data["_id"] = ObjectId()
            plan_data["createdAt"] = datetime.utcnow()
            plan_id = str(plan_data["_id"])

            await self.db.contentPlans.insert_one(plan_data)

            for img in images:
                full_prompt = _build_full_prompt(plan_data, img)
                image_prompt = {
                    "_id": ObjectId(),
                    "sessionId": session_id,
                    "contentPlanId": plan_id,
                    "dayNo": plan_data["dayNo"],
                    "section": plan_data["section"],
                    "imageNo": img.get("imageNo", total_images + 1),
                    "prompt": full_prompt,
                    "status": "QUEUED",
                    "jobId": "",
                    "attempts": 0,
                    "errorMessage": "",
                    "createdAt": datetime.utcnow(),
                    "updatedAt": datetime.utcnow(),
                }
                image_prompts.append(image_prompt)
                total_images += 1

        if image_prompts:
            await self.db.imagePrompts.insert_many(image_prompts)

        await self.session_repo.update_one(session_id, {
            "$set": {
                "status": SessionStatus.PLANNED,
                "totalImages": total_images,
            }
        })

        logger.info("plan_generated", session_id=session_id, plans=len(parsed_plans), images=total_images)

        return {
            "sessionId": session_id,
            "plansGenerated": len(parsed_plans),
            "imagesQueued": total_images,
            "rawOutput": raw_output,
        }
