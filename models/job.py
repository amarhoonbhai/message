"""
Job model — scheduled_jobs, job_logs, and worker_status collections.

This is the heart of the distributed pipeline:
  Scheduler creates jobs → Redis queue → Workers process them.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from core.database import get_database
from core.config import MAX_RETRY_COUNT, RETRY_BASE_DELAY_SECONDS

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEDULED JOBS
# ══════════════════════════════════════════════════════════════════════════════

async def create_job(
    user_id: int,
    phone: str,
    message_id: int,
    groups: List[int],
    run_at: datetime = None,
    copy_mode: bool = False,
) -> dict:
    """
    Create a new scheduled send job.

    Args:
        user_id:    Telegram user ID (owner).
        phone:      Phone number of the sending account.
        message_id: ID of the Saved Message to forward/copy.
        groups:     List of target chat_ids.
        run_at:     When to execute (default: now).
        copy_mode:  True = send_message (copy), False = forward_messages.

    Returns:
        The inserted job document.
    """
    db = get_database()
    now = datetime.utcnow()

    doc = {
        "job_id": str(uuid.uuid4()),
        "user_id": user_id,
        "phone": phone,
        "message_id": message_id,
        "groups": groups,
        "copy_mode": copy_mode,
        "run_at": run_at or now,
        "status": "pending",
        "retry_count": 0,
        "max_retries": MAX_RETRY_COUNT,
        "worker_id": None,
        "error": None,
        "created_at": now,
        "started_at": None,
        "completed_at": None,
    }

    await db.scheduled_jobs.insert_one(doc)
    logger.info(f"Job created: {doc['job_id']} for user {user_id}, {len(groups)} groups")
    return doc


async def get_pending_jobs(limit: int = 100) -> List[dict]:
    """
    Fetch jobs that are ready to run.

    Uses the (status, run_at) compound index for efficient scanning.
    """
    db = get_database()
    now = datetime.utcnow()
    cursor = db.scheduled_jobs.find(
        {"status": "pending", "run_at": {"$lte": now}},
    ).sort("run_at", 1).limit(limit)
    return await cursor.to_list(length=limit)


async def claim_job(job_id: str, worker_id: str) -> Optional[dict]:
    """
    Atomically claim a job for processing.

    Uses findOneAndUpdate to guarantee only one worker can claim a job
    (atomic status transition: queued → processing).
    """
    db = get_database()
    return await db.scheduled_jobs.find_one_and_update(
        {"job_id": job_id, "status": {"$in": ["queued", "pending"]}},
        {"$set": {
            "status": "processing",
            "worker_id": worker_id,
            "started_at": datetime.utcnow(),
        }},
        return_document=True,
    )


async def mark_job_queued(job_id: str) -> bool:
    """Atomically transition a job from pending → queued."""
    db = get_database()
    result = await db.scheduled_jobs.update_one(
        {"job_id": job_id, "status": "pending"},
        {"$set": {"status": "queued"}},
    )
    return result.modified_count > 0


async def complete_job(job_id: str, groups_sent: int = 0):
    """Mark a job as successfully completed."""
    db = get_database()
    await db.scheduled_jobs.update_one(
        {"job_id": job_id},
        {"$set": {
            "status": "done",
            "completed_at": datetime.utcnow(),
            "groups_sent": groups_sent,
        }},
    )


async def fail_job(job_id: str, error: str):
    """
    Handle a failed job — retry or mark as permanently failed.

    Implements exponential backoff: 30s, 60s, 120s, 240s, 480s.
    """
    db = get_database()
    job = await db.scheduled_jobs.find_one({"job_id": job_id})
    if not job:
        return

    retry_count = job.get("retry_count", 0) + 1
    max_retries = job.get("max_retries", MAX_RETRY_COUNT)

    if retry_count >= max_retries:
        # Permanently failed
        await db.scheduled_jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "failed",
                "error": error,
                "retry_count": retry_count,
                "completed_at": datetime.utcnow(),
            }},
        )
        logger.error(f"Job {job_id} permanently failed after {retry_count} retries: {error}")
    else:
        # Schedule retry with exponential backoff
        backoff_seconds = RETRY_BASE_DELAY_SECONDS * (2 ** retry_count)
        retry_at = datetime.utcnow() + timedelta(seconds=backoff_seconds)
        await db.scheduled_jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "pending",
                "error": error,
                "retry_count": retry_count,
                "run_at": retry_at,
                "worker_id": None,
            }},
        )
        logger.info(f"Job {job_id} scheduled for retry #{retry_count} at +{backoff_seconds}s")


async def get_job(job_id: str) -> Optional[dict]:
    """Get a job by its ID."""
    db = get_database()
    return await db.scheduled_jobs.find_one({"job_id": job_id})


async def get_user_jobs(user_id: int, status: str = None, limit: int = 50) -> List[dict]:
    """Get jobs for a specific user, optionally filtered by status."""
    db = get_database()
    query: dict = {"user_id": user_id}
    if status:
        query["status"] = status
    cursor = db.scheduled_jobs.find(query).sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


# ══════════════════════════════════════════════════════════════════════════════
#  JOB LOGS (per-group send results)
# ══════════════════════════════════════════════════════════════════════════════

async def log_job_event(
    job_id: str,
    user_id: int,
    phone: str,
    group_id: int,
    message_id: int,
    status: str,
    error: str = None,
):
    """Log the result of sending a message to a single group."""
    db = get_database()
    await db.job_logs.insert_one({
        "job_id": job_id,
        "user_id": user_id,
        "phone": phone,
        "group_id": group_id,
        "message_id": message_id,
        "status": status,       # sent | failed | flood | skipped
        "error": error,
        "timestamp": datetime.utcnow(),
    })


async def get_job_logs(job_id: str) -> List[dict]:
    """Get all send logs for a specific job."""
    db = get_database()
    cursor = db.job_logs.find({"job_id": job_id}).sort("timestamp", 1)
    return await cursor.to_list(length=10_000)


# ══════════════════════════════════════════════════════════════════════════════
#  WORKER STATUS (heartbeats)
# ══════════════════════════════════════════════════════════════════════════════

async def upsert_worker_heartbeat(
    worker_id: str,
    active_jobs: int = 0,
    total_processed: int = 0,
):
    """Update or create a worker heartbeat entry."""
    db = get_database()
    now = datetime.utcnow()
    await db.worker_status.update_one(
        {"worker_id": worker_id},
        {
            "$set": {
                "last_seen": now,
                "active_jobs": active_jobs,
                "total_processed": total_processed,
            },
            "$setOnInsert": {
                "worker_id": worker_id,
                "started_at": now,
            },
        },
        upsert=True,
    )


async def find_dead_workers(threshold_seconds: int = 120) -> List[dict]:
    """Find workers whose last heartbeat is older than the threshold."""
    db = get_database()
    cutoff = datetime.utcnow() - timedelta(seconds=threshold_seconds)
    cursor = db.worker_status.find({"last_seen": {"$lt": cutoff}})
    return await cursor.to_list(length=1000)


async def reset_stuck_jobs(dead_worker_ids: List[str]) -> int:
    """Reset jobs stuck in 'processing' by dead workers back to 'pending'."""
    if not dead_worker_ids:
        return 0

    db = get_database()
    result = await db.scheduled_jobs.update_many(
        {"status": "processing", "worker_id": {"$in": dead_worker_ids}},
        {"$set": {
            "status": "pending",
            "worker_id": None,
        }},
    )

    if result.modified_count > 0:
        logger.warning(
            f"Reset {result.modified_count} stuck jobs from dead workers: {dead_worker_ids}"
        )

    # Clean up dead worker entries
    await db.worker_status.delete_many({"worker_id": {"$in": dead_worker_ids}})

    return result.modified_count


async def get_all_worker_statuses() -> List[dict]:
    """Get all worker heartbeat entries."""
    db = get_database()
    cursor = db.worker_status.find().sort("last_seen", -1)
    return await cursor.to_list(length=1000)
