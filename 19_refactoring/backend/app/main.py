from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.auth import router as auth_router
from .core.config import ALLOWED_ORIGIN
from .websockets.endpoint import router as ws_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーターの登録
app.include_router(auth_router)
app.include_router(ws_router)
