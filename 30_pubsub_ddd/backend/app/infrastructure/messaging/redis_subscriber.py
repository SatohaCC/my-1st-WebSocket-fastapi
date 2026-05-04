import json

import redis.asyncio as aioredis

from ...core.config import settings
from ...presentation.websockets.manager import manager


async def redis_subscriber() -> None:
    client: aioredis.Redis = aioredis.from_url(settings.REDIS_URL)
    pubsub = client.pubsub()
    await pubsub.subscribe(settings.REDIS_CHANNEL)
    async for raw in pubsub.listen():
        if raw["type"] == "message":
            data = json.loads(raw["data"])
            await manager.broadcast_local(data)
