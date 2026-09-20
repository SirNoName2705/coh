from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.chat import router as chat_router
from src.rag.chroma_manager import rag_manager
from src.core.logger import get_logger

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fährt die 12 CPU-Worker hoch und lädt das BAAI-Modell in deren RAM
    rag_manager.start()
    yield
    # Killt die Worker beim Beenden des Servers sauber
    rag_manager.stop()

def create_app() -> FastAPI:
    app = FastAPI(title="Council of Heroes", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(chat_router)
    return app

app = create_app()

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "service": "council-of-heroes"}