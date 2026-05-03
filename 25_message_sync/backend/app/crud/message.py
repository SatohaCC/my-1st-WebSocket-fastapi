from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.message import Message


async def create_message(db: AsyncSession, username: str, text: str) -> Message:
    """メッセージを DB に保存し、DB が採番した id を含むレコードを返す。"""
    db_message = Message(username=username, text=text)
    db.add(db_message)
    await db.commit()
    await db.refresh(db_message)
    return db_message


async def get_recent_messages(db: AsyncSession, limit: int = 50) -> list[Message]:
    """最新のメッセージ履歴を取得する。"""
    result = await db.execute(
        select(Message).order_by(Message.created_at.desc()).limit(limit)
    )
    # クライアントには古い順に見せたいので reverse する
    messages = list(result.scalars().all())
    messages.reverse()
    return messages


async def get_messages_after(db: AsyncSession, after_id: int) -> list[Message]:
    """指定 ID より後のメッセージを古い順で取得する。再接続時の差分取得に使う。"""
    result = await db.execute(
        select(Message).where(Message.id > after_id).order_by(Message.id.asc())
    )
    return list(result.scalars().all())
