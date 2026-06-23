"""
BullMQ job processor for image generation.
Runs Playwright automation, downloads images, uploads to Google Drive.
"""
import asyncio
import os
from datetime import datetime
from pathlib import Path
from bson import ObjectId
import certifi
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

from worker.processors.flow_automation import generate_image
from app.logging_config import get_logger

logger = get_logger(__name__)

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "persona_ai_studio")

_client: AsyncIOMotorClient | None = None


def _get_db():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGODB_URL, tlsCAFile=certifi.where())
    return _client[MONGODB_DB]


async def _upload_to_drive(local_path: str, session: dict, character: dict, image_no: int) -> dict:
    try:
        from app.services.google_drive_service import GoogleDriveService
        drive = GoogleDriveService()
        date_str = session.get("startDate", datetime.utcnow().strftime("%Y-%m-%d"))
        session_id = str(session["_id"])
        folder_id = drive.get_or_create_session_folder(character["name"], date_str, session_id)
        filename = f"image_{image_no:03d}.jpg"
        result = drive.upload_image(local_path, filename, folder_id)
        return result
    except Exception as e:
        logger.warning("drive_upload_failed", error=str(e))
        return {"fileId": "", "url": ""}


async def process_image_job(job, job_token: str) -> dict:
    data = job.data
    prompt_id = data.get("promptId")
    session_id = data.get("sessionId")
    prompt_text = data.get("prompt")
    image_no = data.get("imageNo", 1)
    day_no = data.get("dayNo", 1)
    section = data.get("section", "")

    db = _get_db()

    logger.info("processing_job", prompt_id=prompt_id, job_id=job.id)

    # Mark as processing
    await db.imagePrompts.update_one(
        {"_id": ObjectId(prompt_id)},
        {"$set": {"status": "PROCESSING", "updatedAt": datetime.utcnow()},
         "$inc": {"attempts": 1}}
    )

    start_time = datetime.utcnow()

    try:
        output_filename = f"{session_id}_{day_no}_{section}_{image_no:03d}.jpg"
        local_path = await generate_image(prompt_text, output_filename)

        session = await db.sessions.find_one({"_id": ObjectId(session_id)})
        character = await db.characters.find_one(
            {"_id": ObjectId(session["characterId"])}
        ) if session else None

        drive_result = {"fileId": "", "url": ""}
        if session and character:
            drive_result = await _upload_to_drive(local_path, session, character, image_no)

        generation_time = (datetime.utcnow() - start_time).total_seconds()

        generated_image = {
            "_id": ObjectId(),
            "imagePromptId": prompt_id,
            "sessionId": session_id,
            "characterId": str(session["characterId"]) if session else "",
            "driveFileId": drive_result.get("fileId", ""),
            "driveUrl": drive_result.get("url", ""),
            "localPath": local_path,
            "generationTime": generation_time,
            "status": "completed",
            "createdAt": datetime.utcnow(),
        }
        await db.generatedImages.insert_one(generated_image)

        await db.imagePrompts.update_one(
            {"_id": ObjectId(prompt_id)},
            {"$set": {"status": "COMPLETED", "updatedAt": datetime.utcnow()}}
        )
        await db.sessions.update_one(
            {"_id": ObjectId(session_id)},
            {"$inc": {"generatedImages": 1}}
        )

        logger.info("job_completed", prompt_id=prompt_id, time=generation_time)
        return {"status": "completed", "driveUrl": drive_result.get("url", "")}

    except Exception as e:
        logger.error("job_failed", prompt_id=prompt_id, error=str(e))

        attempts = data.get("attempts", 0) + 1
        status = "RETRYING" if attempts < 3 else "FAILED"

        await db.imagePrompts.update_one(
            {"_id": ObjectId(prompt_id)},
            {"$set": {
                "status": status,
                "errorMessage": str(e),
                "updatedAt": datetime.utcnow()
            }}
        )

        if status == "FAILED":
            await db.sessions.update_one(
                {"_id": ObjectId(session_id)},
                {"$inc": {"failedImages": 1}}
            )

        raise
