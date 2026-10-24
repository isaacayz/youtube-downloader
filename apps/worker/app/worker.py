import logging
import redis
from rq import Worker, Queue
from app.core.config import worker_settings

logging.basicConfig(level=getattr(logging, worker_settings.LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger("media_worker")


def run_worker():
    listen = ["media_jobs"]
    redis_conn = redis.from_url(worker_settings.REDIS_URL)

    queues = [Queue(name, connection=redis_conn) for name in listen]
    worker = Worker(queues, connection=redis_conn)
    logger.info(f"RQ Worker started on queues: {listen}")
    worker.work()


if __name__ == "__main__":
    run_worker()
