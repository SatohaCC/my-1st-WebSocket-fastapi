import json

import redis.asyncio as aioredis

from ...core.config import settings


class RedisEventPublisher:
    def __init__(self) -> None:
        self._redis: aioredis.Redis = aioredis.from_url(settings.REDIS_URL)

    async def publish(self, event: dict) -> None:
        seq = await self._redis.incr(settings.REDIS_SEQ_KEY)
        await self._redis.publish(settings.REDIS_CHANNEL, json.dumps({**event, "seq": seq}))


event_publisher = RedisEventPublisher()
