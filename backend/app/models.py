import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    creator = "creator"
    teacher = "teacher"
    learner = "learner"


class GameSource(str, enum.Enum):
    upload = "upload"
    template = "template"
    ai = "ai"


class EventType(str, enum.Enum):
    score = "score"
    answer = "answer"
    task_time = "task_time"
    level_complete = "level_complete"
    milestone = "milestone"
    complete = "complete"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.learner)
    llm_provider: Mapped[str | None] = mapped_column(String(16), nullable=True)
    llm_api_key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_api_key_hint: Mapped[str | None] = mapped_column(String(8), nullable=True)
    style_source: Mapped[str] = mapped_column(String(16), nullable=False, default="futureonaut")
    style_guidelines: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    games: Mapped[list["Game"]] = relationship(back_populates="owner")
    sessions: Mapped[list["PlaySession"]] = relationship(back_populates="user")
    stored_llm_keys: Mapped[list["UserLlmKey"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserLlmKey(Base):
    __tablename__ = "user_llm_keys"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_user_llm_keys_provider"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    key_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    key_hint: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="stored_llm_keys")


class Game(Base):
    __tablename__ = "games"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[GameSource] = mapped_column(Enum(GameSource), nullable=False)
    topic_tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    entry_path: Mapped[str] = mapped_column(String(500), nullable=False, default="index.html")
    template_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    seed_file: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    html: Mapped[str | None] = mapped_column(Text, nullable=True)
    handle: Mapped[str | None] = mapped_column(String(120), unique=True, index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped[User | None] = relationship(back_populates="games")
    sessions: Mapped[list["PlaySession"]] = relationship(back_populates="game")
    views: Mapped[list["GameView"]] = relationship(back_populates="game")


class GameDraft(Base):
    __tablename__ = "game_drafts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    topic: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    level_count: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    provider: Mapped[str] = mapped_column(String(16), nullable=False, default="openai")
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    html: Mapped[str] = mapped_column(Text, nullable=False)
    messages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    assign_classroom_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    published_game_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_game_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped[User] = relationship()


class GameView(Base):
    __tablename__ = "game_views"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("games.id"), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    visitor_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    game: Mapped[Game] = relationship(back_populates="views")
    user: Mapped[User | None] = relationship()


class PlaySession(Base):
    __tablename__ = "play_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    visitor_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    game_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("games.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_time_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    levels_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_levels: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user: Mapped[User | None] = relationship(back_populates="sessions")
    game: Mapped[Game] = relationship(back_populates="sessions")
    events: Mapped[list["SessionEvent"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class Classroom(Base):
    __tablename__ = "classrooms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    join_code: Mapped[str] = mapped_column(String(8), unique=True, index=True, nullable=False)
    teacher_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    teacher: Mapped[User] = relationship(foreign_keys=[teacher_id])
    members: Mapped[list["ClassroomMember"]] = relationship(back_populates="classroom", cascade="all, delete-orphan")
    assignments: Mapped[list["ClassroomAssignment"]] = relationship(
        back_populates="classroom", cascade="all, delete-orphan"
    )


class ClassroomMember(Base):
    __tablename__ = "classroom_members"
    __table_args__ = (UniqueConstraint("classroom_id", "user_id", name="uq_classroom_member"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    classroom_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("classrooms.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    classroom: Mapped[Classroom] = relationship(back_populates="members")
    user: Mapped[User] = relationship()


class ClassroomAssignment(Base):
    __tablename__ = "classroom_assignments"
    __table_args__ = (UniqueConstraint("classroom_id", "game_id", name="uq_classroom_assignment"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    classroom_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("classrooms.id"), nullable=False)
    game_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("games.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    classroom: Mapped[Classroom] = relationship(back_populates="assignments")
    game: Mapped[Game] = relationship()


class GameLike(Base):
    __tablename__ = "game_likes"
    __table_args__ = (UniqueConstraint("user_id", "game_id", name="uq_game_like_user_game"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    game_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("games.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship()
    game: Mapped[Game] = relationship()


class GameComment(Base):
    __tablename__ = "game_comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("games.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship()
    game: Mapped[Game] = relationship()


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


class PlatformSettings(Base):
    __tablename__ = "platform_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    style_guidelines: Mapped[str] = mapped_column(Text, nullable=False, default="")
    generation_system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    revise_system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    catalog_assigned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
