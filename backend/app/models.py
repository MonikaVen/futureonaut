import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    creator = "creator"
    learner = "learner"


class GameSource(str, enum.Enum):
    upload = "upload"
    template = "template"
    ai = "ai"


class EventType(str, enum.Enum):
    score = "score"
    answer = "answer"
    task_time = "task_time"
    complete = "complete"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.learner)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    games: Mapped[list["Game"]] = relationship(back_populates="owner")
    sessions: Mapped[list["PlaySession"]] = relationship(back_populates="user")


class Game(Base):
    __tablename__ = "games"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    source: Mapped[GameSource] = mapped_column(Enum(GameSource), nullable=False)
    topic_tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    entry_path: Mapped[str] = mapped_column(String(500), nullable=False, default="index.html")
    template_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    files: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped[User] = relationship(back_populates="games")
    sessions: Mapped[list["PlaySession"]] = relationship(back_populates="game")


class PlaySession(Base):
    __tablename__ = "play_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    game_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("games.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_time_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user: Mapped[User] = relationship(back_populates="sessions")
    game: Mapped[Game] = relationship(back_populates="sessions")
    events: Mapped[list["SessionEvent"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class SessionEvent(Base):
    __tablename__ = "session_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("play_sessions.id"), nullable=False
    )
    type: Mapped[EventType] = mapped_column(Enum(EventType), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[PlaySession] = relationship(back_populates="events")
