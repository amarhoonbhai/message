"""
ARQ queue integration — job definitions, enqueue helper, worker settings.
"""

import logging
from arq.connections import ArqRedis

from core.redis_client import get_redis_pool, get_redis_settings
from core.config import WORKER_CONCURRENCY

logger = logging.getLogger(__name__)


async def enqueue_send_job(pool: ArqRedis, job_id: str):
    """
    Enqueue a send job into the Redis queue for ARQ workers to pick up.

    Args:
        pool:   An ARQ Redis connection pool.
        job_id: The scheduled_jobs.job_id to process.
    """
    await pool.enqueue_job("send_job", job_id=job_id)
    logger.debug(f"Enqueued job {job_id}")
