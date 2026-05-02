from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.auth import router as auth_router
from .core.config import settings
from .db.session import engine
from .models.message import Base
from .websockets.endpoint import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- 起動時の処理: テーブル作成 ---
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables initialized.")
    yield
    # --- 終了時の処理 ---
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.ALLOWED_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーターの登録
app.include_router(auth_router)
app.include_router(ws_router)
