from ...domain.repositories.event_publisher import EventPublisher
from ...domain.repositories.message_repository import MessageRepository


class SendMessageUseCase:
    def __init__(self, repo: MessageRepository, publisher: EventPublisher) -> None:
        self._repo = repo
        self._publisher = publisher

    async def execute(self, username: str, text: str) -> None:
        message = await self._repo.save(username, text)
        await self._publisher.publish({
            "type": "message",
            "username": message.username,
            "text": message.text,
            "id": message.id,
        })
