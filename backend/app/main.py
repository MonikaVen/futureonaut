from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.database import Base, engine
from app.routers import auth, games, sessions
from app.routers.dashboard import admin_router, router as dashboard_router
from app.seed import seed_admin
from app.services.demo_seed import seed_demo_games


def ensure_schema() -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE games ADD COLUMN IF NOT EXISTS source_language VARCHAR(16) "
                "NOT NULL DEFAULT 'en'"
            )
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    Path(settings.games_dir).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    seed_admin()
    seed_demo_games()
    yield


app = FastAPI(title="Futureonaut API", version="1.0.0", lifespan=lifespan)
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(games.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(admin_router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
