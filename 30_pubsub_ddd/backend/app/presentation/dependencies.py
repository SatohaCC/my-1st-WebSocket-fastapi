from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.repositories.event_publisher import EventPublisher
from ..domain.repositories.message_repository import MessageRepository
from ..infrastructure.messaging.redis_publisher import event_publisher as _event_publisher
from ..infrastructure.persistence.sa_message_repository import SqlAlchemyMessageRepository
from ..infrastructure.persistence.session import get_db


def get_message_repo(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageRepository:
    return SqlAlchemyMessageRepository(db)


def get_event_publisher() -> EventPublisher:
    return _event_publisher
