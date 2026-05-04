from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...domain.entities.message import Message
from .orm_models import OrmMessage


class SqlAlchemyMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, username: str, text: str) -> Message:
        orm_msg = OrmMessage(username=username, text=text)
        self._session.add(orm_msg)
        await self._session.commit()
        await self._session.refresh(orm_msg)
        return self._to_domain(orm_msg)

    async def get_after(self, after_id: int) -> list[Message]:
        result = await self._session.execute(
            select(OrmMessage).where(OrmMessage.id > after_id).order_by(OrmMessage.id.asc())
        )
        return [self._to_domain(m) for m in result.scalars().all()]

    async def get_recent(self, limit: int = 50) -> list[Message]:
        result = await self._session.execute(
            select(OrmMessage).order_by(OrmMessage.created_at.desc()).limit(limit)
        )
        msgs = [self._to_domain(m) for m in result.scalars().all()]
        msgs.reverse()
        return msgs

    @staticmethod
    def _to_domain(orm_msg: OrmMessage) -> Message:
        return Message(
            id=orm_msg.id,
            username=orm_msg.username,
            text=orm_msg.text,
            created_at=orm_msg.created_at,
        )
