import redis
from rq import Queue
from app.core.config import settings

redis_client = redis.from_url(settings.REDIS_URL)
media_queue = Queue("media_jobs", connection=redis_client)


def get_redis_client():
    return redis_client


def get_queue():
    return media_queue
