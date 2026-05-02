import asyncio

from app.db.session import engine
from app.models.message import Base


async def init_db():
    async with engine.begin() as conn:
        # テーブルを全て作成 (Message テーブルなど)
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully.")


if __name__ == "__main__":
    asyncio.run(init_db())
