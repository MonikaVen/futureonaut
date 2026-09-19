import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.models import EventType, GameSource, UserRole


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=120)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: UserRole
    created_at: datetime

    model_config = {"from_attributes": True}


class UserRoleUpdate(BaseModel):
    role: UserRole


class GameOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    owner_id: uuid.UUID
    owner_name: str | None = None
    source: GameSource
    topic_tags: list[str]
    difficulty: int
    entry_path: str
    template_type: str | None
    source_language: str = "en"
    created_at: datetime
    play_url: str | None = None

    model_config = {"from_attributes": True}


class GameUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = None
    topic_tags: list[str] | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)


class QuizOption(BaseModel):
    text: str
    correct: bool = False


class QuizQuestion(BaseModel):
    id: str
    prompt: str
    options: list[QuizOption]
    points: int = 10


class QuizContent(BaseModel):
    title: str
    description: str = ""
    topic_tags: list[str] = Field(default_factory=list)
    difficulty: int = Field(default=1, ge=1, le=5)
    questions: list[QuizQuestion]


class DragPair(BaseModel):
    id: str
    left: str
    right: str
    points: int = 10


class DragMatchContent(BaseModel):
    title: str
    description: str = ""
    topic_tags: list[str] = Field(default_factory=list)
    difficulty: int = Field(default=1, ge=1, le=5)
    pairs: list[DragPair]


class TimedItem(BaseModel):
    id: str
    prompt: str
    answer: str
    points: int = 10
    time_limit_ms: int = 30000


class TimedChallengeContent(BaseModel):
    title: str
    description: str = ""
    topic_tags: list[str] = Field(default_factory=list)
    difficulty: int = Field(default=1, ge=1, le=5)
    items: list[TimedItem]


class TemplateGameCreate(BaseModel):
    template_type: str
    content: dict[str, Any]


class AIGenerateRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    difficulty: int = Field(default=1, ge=1, le=5)
    template_type: str = Field(default="quiz")
    description: str = ""
    question_count: int = Field(default=5, ge=3, le=12)


class SessionCreate(BaseModel):
    game_id: uuid.UUID


class SessionEventIn(BaseModel):
    type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)


class SessionOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    game_id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None
    total_points: int
    total_time_ms: int
    correct_count: int
    attempt_count: int

    model_config = {"from_attributes": True}


class SessionDetail(SessionOut):
    game_title: str | None = None


class DashboardStats(BaseModel):
    total_sessions: int
    total_points: int
    avg_accuracy: float
    avg_task_time_ms: float
    recent_sessions: list[SessionDetail]
    per_game: list[dict[str, Any]]
    by_topic: list[dict[str, Any]]


class PlatformStats(BaseModel):
    users: int
    games: int
    sessions: int
    creators: int
    learners: int


class RecommendationOut(BaseModel):
    game: GameOut
    reason: str
    score: float
