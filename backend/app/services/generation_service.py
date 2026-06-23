import asyncio
from datetime import datetime, timedelta
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.repositories.character_repository import CharacterRepository
from app.repositories.batch_repository import BatchRepository
from app.repositories.day_section_repository import DaySectionRepository
from app.services.gemini_service import GeminiService
from app.models.batch import BatchStatus
from app.logging_config import get_logger

logger = get_logger(__name__)

_RETRY_DELAYS = [30, 60, 90]  # seconds between retries on rate limit


async def _generate_section_with_retry(gemini: GeminiService, **kwargs) -> dict:
    last_exc = None
    for attempt, delay in enumerate([0] + _RETRY_DELAYS):
        if delay:
            logger.warning("rate_limit_backoff", delay=delay, attempt=attempt)
            await asyncio.sleep(delay)
        try:
            return await gemini.generate_single_section(**kwargs)
        except Exception as e:
            last_exc = e
            err = str(e).lower()
            # Only retry on rate limit / server errors
            if any(k in err for k in ("rate_limit", "429", "too many", "tokens", "503", "502", "timed out", "timeout", "json_validate_failed", "sorry", "can't help", "cannot help")):
                logger.warning("retrying_section", attempt=attempt + 1, error=str(e)[:120])
                continue
            raise  # non-retriable error, fail immediately
    raise last_exc


class GenerationService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.character_repo = CharacterRepository(db)
        self.batch_repo = BatchRepository(db)
        self.section_repo = DaySectionRepository(db)
        self.gemini = GeminiService()

    async def generate_batch(self, batch_id: str) -> dict:
        try:
            return await self._generate(batch_id)
        except Exception as exc:
            logger.error("batch_generation_failed", batch_id=batch_id, error=str(exc))
            await self.batch_repo.update_one(
                batch_id,
                {"$set": {"status": BatchStatus.FAILED, "errorMessage": str(exc), "updatedAt": datetime.utcnow()}}
            )
            raise

    async def _generate(self, batch_id: str) -> dict:
        batch = await self.batch_repo.find_by_id(batch_id)
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")

        character = await self.character_repo.find_by_id(batch["characterId"])
        if not character:
            raise ValueError(f"Character {batch['characterId']} not found")

        sections_config = batch["sections"]
        start = datetime.strptime(batch["startDate"], "%Y-%m-%d")
        end = datetime.strptime(batch["endDate"], "%Y-%m-%d")
        num_days = (end - start).days + 1
        num_sections_per_day = len(sections_config)
        total_sections = num_days * num_sections_per_day

        # Load already-generated sections to skip them (resume support)
        existing_docs = await self.section_repo.find_by_batch(batch_id)
        already_done = {(d["dayNo"], d["sectionName"]) for d in existing_docs}
        already_done_count = len(already_done)

        await self.batch_repo.update_one(
            batch_id,
            {"$set": {
                "status": BatchStatus.GENERATING,
                "totalSections": total_sections,
                "generatedSections": already_done_count,
                "updatedAt": datetime.utcnow(),
            }}
        )

        previous_summaries = await self.section_repo.get_recent_summaries(character["_id"])

        total_images = sum(len(d.get("imageDescriptions", [])) for d in existing_docs)
        failed_days = []
        call_no = 0

        for day_no in range(1, num_days + 1):
            date_str = (start + timedelta(days=day_no - 1)).strftime("%Y-%m-%d")
            logger.info("generating_day", batch_id=batch_id, day=day_no, total=num_days)

            day_failed = False

            for sec_idx, section in enumerate(sections_config):
                call_no += 1

                # Skip sections already successfully generated
                if (day_no, section["name"]) in already_done:
                    logger.info("skipping_existing_section", batch_id=batch_id, day=day_no, section=section["name"])
                    continue

                try:
                    plan = await _generate_section_with_retry(
                        self.gemini,
                        character=character,
                        day_no=day_no,
                        date_str=date_str,
                        section=section,
                        content_summary=batch.get("contentSummary", ""),
                        previous_summaries=previous_summaries,
                    )
                except Exception as e:
                    logger.error("section_generation_failed", batch_id=batch_id, day=day_no,
                                 section=section["name"], error=str(e))
                    day_failed = True
                    if call_no < total_sections:
                        await asyncio.sleep(3)
                    continue

                section_docs = []
                for day_data in plan.get("days", [plan]):
                    for sec in day_data.get("sections", []):
                        shared = sec.get("sharedDescription", {})
                        section_docs.append({
                            "_id": ObjectId(),
                            "batchId": batch_id,
                            "dayNo": day_no,
                            "date": date_str,
                            "sectionName": sec.get("sectionName", section["name"]),
                            "sectionOrder": sec_idx,
                            "contentType": sec.get("contentType", ""),
                            "sectionIntent": sec.get("sectionIntent", ""),
                            "contentSummary": sec.get("contentSummary", ""),
                            "outfitFamily": shared.get("outfitFamily", ""),
                            "lightingMood": shared.get("lightingMood", ""),
                            "cameraStyle": shared.get("cameraStyle", ""),
                            "backgroundLocation": shared.get("backgroundLocation", ""),
                            "hashtags": sec.get("hashtags", []),
                            "imageDescriptions": sec.get("imageDescriptions", []),
                            "createdAt": datetime.utcnow(),
                        })
                        total_images += len(sec.get("imageDescriptions", []))

                if section_docs:
                    await self.db.daySections.insert_many(section_docs)
                    await self.batch_repo.update_one(
                        batch_id, {"$inc": {"generatedSections": 1}}
                    )

                # Small delay between section calls
                if call_no < total_sections:
                    await asyncio.sleep(3)

            if day_failed:
                failed_days.append(day_no)

        error_msg = f"Days failed: {failed_days}" if failed_days else ""
        if len(failed_days) == num_days:
            final_status = BatchStatus.FAILED
        elif failed_days:
            final_status = BatchStatus.PARTIAL
        else:
            final_status = BatchStatus.COMPLETED
        await self.batch_repo.update_one(batch_id, {
            "$set": {
                "status": final_status,
                "totalImages": total_images,
                "errorMessage": error_msg,
                "updatedAt": datetime.utcnow(),
            }
        })

        logger.info("batch_generated", batch_id=batch_id, days=num_days,
                    failed=len(failed_days), images=total_images)
        return {"batchId": batch_id, "daysGenerated": num_days - len(failed_days),
                "daysFailed": failed_days, "totalImages": total_images}

    async def regenerate_section(self, batch_id: str, day_no: int, section_name: str) -> dict:
        """Regenerate a single day+section and upsert the DaySection document."""
        batch = await self.batch_repo.find_by_id(batch_id)
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")

        character = await self.character_repo.find_by_id(batch["characterId"])
        if not character:
            raise ValueError("Character not found")

        sections_config = batch["sections"]
        section_config = next((s for s in sections_config if s["name"] == section_name), None)
        if not section_config:
            raise ValueError(f"Section '{section_name}' not found in batch config")

        sec_idx = next((i for i, s in enumerate(sections_config) if s["name"] == section_name), 0)
        start = datetime.strptime(batch["startDate"], "%Y-%m-%d")
        date_str = (start + timedelta(days=day_no - 1)).strftime("%Y-%m-%d")
        previous_summaries = await self.section_repo.get_recent_summaries(character["_id"])

        plan = await _generate_section_with_retry(
            self.gemini,
            character=character,
            day_no=day_no,
            date_str=date_str,
            section=section_config,
            content_summary=batch.get("contentSummary", ""),
            previous_summaries=previous_summaries,
        )

        # Delete existing section for this day before inserting new one
        await self.db.daySections.delete_one(
            {"batchId": batch_id, "dayNo": day_no, "sectionName": section_name}
        )

        inserted = None
        for day_data in plan.get("days", [plan]):
            for sec in day_data.get("sections", []):
                shared = sec.get("sharedDescription", {})
                doc = {
                    "_id": ObjectId(),
                    "batchId": batch_id,
                    "dayNo": day_no,
                    "date": date_str,
                    "sectionName": sec.get("sectionName", section_name),
                    "sectionOrder": sec_idx,
                    "contentType": sec.get("contentType", ""),
                    "sectionIntent": sec.get("sectionIntent", ""),
                    "contentSummary": sec.get("contentSummary", ""),
                    "outfitFamily": shared.get("outfitFamily", ""),
                    "lightingMood": shared.get("lightingMood", ""),
                    "cameraStyle": shared.get("cameraStyle", ""),
                    "backgroundLocation": shared.get("backgroundLocation", ""),
                    "hashtags": sec.get("hashtags", []),
                    "imageDescriptions": sec.get("imageDescriptions", []),
                    "createdAt": datetime.utcnow(),
                }
                await self.db.daySections.insert_one(doc)
                doc["_id"] = str(doc["_id"])
                inserted = doc
                break
            if inserted:
                break

        if not inserted:
            raise ValueError("No section data returned from AI")

        logger.info("section_regenerated", batch_id=batch_id, day=day_no, section=section_name)
        return inserted
