import os
import logging
from celery import Celery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pharmyrus-worker")

ROLE = os.getenv("ROLE", "api")
REDIS_URL = os.getenv("REDIS_URL")

if ROLE != "worker":
    logger.info("🚫 Celery disabled (ROLE != worker)")
    app = None
else:
    if not REDIS_URL:
        raise RuntimeError("❌ REDIS_URL is required for worker")

    logger.info("✅ Starting Celery worker")
    logger.info(f"🔌 Redis: {REDIS_URL[:40]}...")

    app = Celery(
        "pharmyrus",
        broker=REDIS_URL,
        backend=REDIS_URL,
        include=["tasks"]
    )

    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        broker_connection_retry_on_startup=True,
        worker_prefetch_multiplier=1,
        task_time_limit=3600,
        task_soft_time_limit=3300,
        result_expires=86400,
    )
