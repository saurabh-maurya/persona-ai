"""
BullMQ Worker Entry Point.
Run with: python -m worker.main
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bullmq import Worker
from app.logging_config import configure_logging, get_logger
from worker.processors.image_processor import process_image_job

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
QUEUE_NAME = os.getenv("QUEUE_NAME", "image-generation")
WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "2"))

logger = get_logger(__name__)


async def main():
    configure_logging(debug=os.getenv("DEBUG", "false").lower() == "true")

    connection = {"host": REDIS_HOST, "port": REDIS_PORT}
    if REDIS_PASSWORD:
        connection["password"] = REDIS_PASSWORD

    logger.info("worker_starting", queue=QUEUE_NAME, concurrency=WORKER_CONCURRENCY)

    worker = Worker(
        QUEUE_NAME,
        process_image_job,
        {
            "connection": connection,
            "concurrency": WORKER_CONCURRENCY,
            "lockDuration": 300_000,
        }
    )

    worker.on("completed", lambda job, result: logger.info("job_done", job_id=job.id))
    worker.on("failed", lambda job, err: logger.error("job_error", job_id=job.id if job else "?", error=str(err)))

    logger.info("worker_ready", queue=QUEUE_NAME)

    try:
        while True:
            await asyncio.sleep(5)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("worker_stopping")
        await worker.close()


if __name__ == "__main__":
    asyncio.run(main())
