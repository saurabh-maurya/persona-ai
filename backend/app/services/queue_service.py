from bullmq import Queue
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.config import get_settings
from app.repositories.image_prompt_repository import ImagePromptRepository
from app.repositories.session_repository import SessionRepository
from app.models.image_prompt import PromptStatus
from app.models.session import SessionStatus
from app.logging_config import get_logger

logger = get_logger(__name__)


def _redis_connection(settings) -> dict:
    conn = {"host": settings.redis_host, "port": settings.redis_port}
    if settings.redis_password:
        conn["password"] = settings.redis_password
    return conn


class QueueService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.settings = get_settings()
        self.image_prompt_repo = ImagePromptRepository(db)
        self.session_repo = SessionRepository(db)
        self._queue: Queue | None = None

    def _get_queue(self) -> Queue:
        if self._queue is None:
            self._queue = Queue(
                self.settings.queue_name,
                {"connection": _redis_connection(self.settings)}
            )
        return self._queue

    async def enqueue_session(self, session_id: str) -> int:
        prompts = await self.image_prompt_repo.find_by_session(session_id)
        queued = 0
        queue = self._get_queue()

        for prompt in prompts:
            if prompt["status"] in (PromptStatus.QUEUED, PromptStatus.FAILED):
                job = await queue.add(
                    "generate-image",
                    {
                        "promptId": prompt["_id"],
                        "sessionId": session_id,
                        "prompt": prompt["prompt"],
                        "dayNo": prompt["dayNo"],
                        "section": prompt["section"],
                        "imageNo": prompt["imageNo"],
                    },
                    {
                        "attempts": self.settings.max_retries,
                        "backoff": {"type": "exponential", "delay": 5000},
                        "timeout": self.settings.job_timeout_ms,
                    }
                )
                await self.image_prompt_repo.update_one(
                    prompt["_id"],
                    {"$set": {"status": PromptStatus.QUEUED, "jobId": job.id}}
                )
                queued += 1

        await self.session_repo.update_one(session_id, {
            "$set": {"status": SessionStatus.GENERATING}
        })

        logger.info("session_enqueued", session_id=session_id, jobs=queued)
        return queued

    async def retry_failed(self, session_id: str | None = None, prompt_id: str | None = None) -> int:
        queue = self._get_queue()
        retried = 0

        if prompt_id:
            prompt = await self.image_prompt_repo.find_by_id(prompt_id)
            if prompt and prompt["status"] == PromptStatus.FAILED:
                job = await queue.add(
                    "generate-image",
                    {"promptId": prompt["_id"], "sessionId": prompt["sessionId"],
                     "prompt": prompt["prompt"], "dayNo": prompt["dayNo"],
                     "section": prompt["section"], "imageNo": prompt["imageNo"]},
                    {"attempts": self.settings.max_retries,
                     "backoff": {"type": "exponential", "delay": 5000}}
                )
                await self.image_prompt_repo.update_one(
                    prompt_id,
                    {"$set": {"status": PromptStatus.QUEUED, "jobId": job.id, "attempts": 0}}
                )
                retried += 1
        elif session_id:
            failed = await self.image_prompt_repo.find_failed(session_id)
            for prompt in failed:
                job = await queue.add(
                    "generate-image",
                    {"promptId": prompt["_id"], "sessionId": session_id,
                     "prompt": prompt["prompt"], "dayNo": prompt["dayNo"],
                     "section": prompt["section"], "imageNo": prompt["imageNo"]},
                    {"attempts": self.settings.max_retries,
                     "backoff": {"type": "exponential", "delay": 5000}}
                )
                await self.image_prompt_repo.update_one(
                    prompt["_id"],
                    {"$set": {"status": PromptStatus.QUEUED, "jobId": job.id, "attempts": 0}}
                )
                retried += 1

        logger.info("jobs_retried", count=retried)
        return retried

    async def get_status(self, session_id: str) -> dict:
        counts = await self.image_prompt_repo.count_by_status(session_id)
        return {
            "sessionId": session_id,
            "queued": counts.get("QUEUED", 0),
            "processing": counts.get("PROCESSING", 0),
            "completed": counts.get("COMPLETED", 0),
            "failed": counts.get("FAILED", 0),
            "retrying": counts.get("RETRYING", 0),
            "total": sum(counts.values()),
        }

    async def get_global_status(self) -> dict:
        counts = await self.image_prompt_repo.count_all_by_status()
        return {
            "pending": counts.get("QUEUED", 0),
            "processing": counts.get("PROCESSING", 0),
            "completed": counts.get("COMPLETED", 0),
            "failed": counts.get("FAILED", 0),
            "retrying": counts.get("RETRYING", 0),
            "total": sum(counts.values()),
        }

    async def close(self):
        if self._queue:
            await self._queue.close()
