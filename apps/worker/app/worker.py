import logging
from datetime import datetime, timezone
import redis
from rq import Worker, Queue
from sqlalchemy import select
from app.core.config import worker_settings
from app.db.session import SessionLocal
from app.models.job import Job
from app.models.job_event import JobEvent

logging.basicConfig(level=getattr(logging, worker_settings.LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger("media_worker")


def reconcile_abandoned_jobs(redis_conn):
    """
    On worker startup, reconcile jobs left in transient states from previous crashed runs.
    """
    db = SessionLocal()
    try:
        query = select(Job).filter(Job.status.in_(["inspecting", "processing"]))
        abandoned_jobs = db.execute(query).scalars().all()

        if abandoned_jobs:
            logger.info(f"Reconciling {len(abandoned_jobs)} abandoned jobs...")
            queue = Queue("media_jobs", connection=redis_conn)
            now = datetime.now(timezone.utc)

            for job in abandoned_jobs:
                if job.attempt_count < job.max_attempts:
                    logger.info(f"Re-queueing abandoned job {job.id} (attempt {job.attempt_count}/{job.max_attempts})")
                    job.status = "queued"
                    job.phase = "re-queued"
                    job.updated_at = now
                    event = JobEvent(
                        job_id=job.id,
                        event_type="job_reconciled",
                        phase="re-queued",
                        progress_percent=0,
                        safe_message="Job reconciled after worker restart and returned to queue.",
                        created_at=now,
                    )
                    db.add(event)
                    queue.enqueue("app.jobs.processor.process_media_job", str(job.id))
                else:
                    logger.warning(f"Marking job {job.id} as failed after exhausting attempts across worker restarts")
                    job.status = "failed"
                    job.last_error_code = "WORKER_CRASH_RECOVERED"
                    job.last_error_safe_message = "Execution failed due to ungraceful worker termination."
                    job.updated_at = now
                    event = JobEvent(
                        job_id=job.id,
                        event_type="job_failed",
                        phase="error",
                        progress_percent=0,
                        safe_message=job.last_error_safe_message,
                        created_at=now,
                    )
                    db.add(event)
            db.commit()
    except Exception as exc:
        logger.error(f"Error during job reconciliation: {exc}")
        db.rollback()
    finally:
        db.close()


def run_worker():
    listen = ["media_jobs"]
    redis_conn = redis.from_url(worker_settings.REDIS_URL)

    # Reconcile any orphaned jobs from past crashes
    reconcile_abandoned_jobs(redis_conn)

    queues = [Queue(name, connection=redis_conn) for name in listen]
    worker = Worker(queues, connection=redis_conn)
    logger.info(f"RQ Worker started on queues: {listen}")
    worker.work()


if __name__ == "__main__":
    run_worker()
