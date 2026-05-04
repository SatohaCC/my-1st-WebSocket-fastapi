import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .infrastructure.messaging.redis_subscriber import redis_subscriber
from .infrastructure.persistence.orm_models import Base
from .infrastructure.persistence.session import engine
from .presentation.api.auth import router as auth_router
from .presentation.api.messages import router as messages_router
from .presentation.websockets.endpoint import router as ws_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables initialized.")
    task = asyncio.create_task(redis_subscriber())
    yield
    task.cancel()
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.ALLOWED_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(messages_router)
app.include_router(ws_router)
