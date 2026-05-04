from typing import Protocol


class EventPublisher(Protocol):
    async def publish(self, event: dict) -> None: ...
