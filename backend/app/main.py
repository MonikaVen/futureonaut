from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.database import Base, engine
from app.routers import auth, classrooms, creator, games, sessions, social
from app.routers.dashboard import admin_router, router as dashboard_router
from app.routers.share_page import router as share_page_router
from app.seed import seed_admin, seed_creator, seed_teacher
from app.services.demo_seed import seed_demo_games


def ensure_schema() -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE games ADD COLUMN IF NOT EXISTS source_language VARCHAR(16) "
                "NOT NULL DEFAULT 'en'"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE play_sessions ADD COLUMN IF NOT EXISTS levels_completed "
                "INTEGER NOT NULL DEFAULT 0"
            )
        )
        conn.execute(
            text("ALTER TABLE play_sessions ADD COLUMN IF NOT EXISTS total_levels INTEGER")
        )
        conn.execute(
            text(
                """
                DO $$ BEGIN
                    ALTER TYPE eventtype ADD VALUE 'level_complete';
                EXCEPTION
                    WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )
        conn.execute(
            text(
                """
                DO $$ BEGIN
                    ALTER TYPE eventtype ADD VALUE 'milestone';
                EXCEPTION
                    WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )
        conn.execute(
            text("ALTER TABLE game_views ADD COLUMN IF NOT EXISTS visitor_id VARCHAR(64)")
        )
        conn.execute(
            text("ALTER TABLE play_sessions ALTER COLUMN user_id DROP NOT NULL")
        )
        conn.execute(
            text("ALTER TABLE play_sessions ADD COLUMN IF NOT EXISTS visitor_id VARCHAR(64)")
        )
        conn.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS llm_provider VARCHAR(16)"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS llm_api_key_hash VARCHAR(64)"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS llm_api_key_hint VARCHAR(8)"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE games ADD COLUMN IF NOT EXISTS seed_file VARCHAR(200)"
            )
        )
        conn.execute(
            text(
                """
                DO $$ BEGIN
                    ALTER TYPE userrole ADD VALUE 'teacher';
                EXCEPTION
                    WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS game_drafts (
                    id UUID PRIMARY KEY,
                    owner_id UUID NOT NULL REFERENCES users(id),
                    title VARCHAR(200) NOT NULL,
                    topic VARCHAR(200) NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    difficulty INTEGER NOT NULL DEFAULT 2,
                    level_count INTEGER NOT NULL DEFAULT 4,
                    language VARCHAR(16) NOT NULL DEFAULT 'en',
                    provider VARCHAR(16) NOT NULL DEFAULT 'openai',
                    model VARCHAR(80),
                    html TEXT NOT NULL,
                    messages JSONB NOT NULL DEFAULT '[]'::jsonb,
                    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
                    assign_classroom_id UUID,
                    published_game_id UUID,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ DEFAULT now()
                )
                """
            )
        )
        conn.execute(
            text("ALTER TABLE games ADD COLUMN IF NOT EXISTS html TEXT")
        )
        conn.execute(
            text("ALTER TABLE games ADD COLUMN IF NOT EXISTS handle VARCHAR(120)")
        )
        conn.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS ix_games_handle ON games (handle)")
        )
        conn.execute(
            text("ALTER TABLE game_drafts ADD COLUMN IF NOT EXISTS source_game_id UUID")
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_game_drafts_owner_id ON game_drafts (owner_id)"
            )
        )
        conn.execute(text("ALTER TABLE games ALTER COLUMN owner_id DROP NOT NULL"))
        conn.execute(
            text(
                """
                DO $$
                DECLARE
                    rec RECORD;
                BEGIN
                    FOR rec IN
                        SELECT con.conname, pg_get_constraintdef(con.oid) AS def
                        FROM pg_constraint con
                        JOIN pg_class rel ON rel.oid = con.conrelid
                        WHERE rel.relname = 'games'
                          AND con.contype = 'f'
                          AND pg_get_constraintdef(con.oid) ILIKE '%owner_id%'
                    LOOP
                        IF rec.def NOT ILIKE '%ON DELETE SET NULL%' THEN
                            EXECUTE format('ALTER TABLE games DROP CONSTRAINT %I', rec.conname);
                        END IF;
                    END LOOP;
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'games_owner_id_fkey'
                    ) THEN
                        ALTER TABLE games
                            ADD CONSTRAINT games_owner_id_fkey
                            FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE SET NULL;
                    END IF;
                END $$;
                """
            )
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    Path(settings.games_dir).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    seed_admin()
    seed_teacher()
    seed_creator()
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
app.include_router(social.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(classrooms.router, prefix="/api")
app.include_router(creator.router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(share_page_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
