import redis.asyncio as redis

from app.config import settings

# A single shared client. It keeps its own connection pool internally.
redis_client = redis.from_url(settings.redis_url, decode_responses=True)
