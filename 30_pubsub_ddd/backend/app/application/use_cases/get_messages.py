from ...domain.entities.message import Message
from ...domain.repositories.message_repository import MessageRepository


class GetMessagesUseCase:
    def __init__(self, repo: MessageRepository) -> None:
        self._repo = repo

    async def execute_after(self, after_id: int) -> list[Message]:
        return await self._repo.get_after(after_id)

    async def execute_recent(self, limit: int = 50) -> list[Message]:
        return await self._repo.get_recent(limit)
