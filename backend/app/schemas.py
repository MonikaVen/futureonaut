import json
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.limits import (
    MAX_EVENT_PAYLOAD_BYTES,
    MAX_EVENT_PAYLOAD_KEY_LEN,
    MAX_EVENT_PAYLOAD_KEYS,
    cap_event_payload,
)
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
    visitor_id: str | None = Field(default=None, max_length=64)


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    visitor_id: str | None = Field(default=None, max_length=64)


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
    source: GameSource
    topic_tags: list[str]
    difficulty: int
    entry_path: str
    template_type: str | None
    source_language: str = "en"
    created_at: datetime
    play_url: str | None = None
    like_count: int = 0
    comment_count: int = 0
    view_count: int = 0
    liked_by_me: bool = False
    completed: bool = False
    levels_completed: int = 0
    total_levels: int | None = None
    progress_pct: int | None = None

    model_config = {"from_attributes": True}


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class CommentOut(BaseModel):
    id: uuid.UUID
    game_id: uuid.UUID
    user_id: uuid.UUID
    author_name: str
    body: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LikeToggleOut(BaseModel):
    liked: bool
    like_count: int


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


class GuestSessionCreate(BaseModel):
    game_id: uuid.UUID
    visitor_id: str = Field(min_length=8, max_length=64)


class GuestMergeIn(BaseModel):
    visitor_id: str = Field(min_length=8, max_length=64)


class SessionEventIn(BaseModel):
    type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        if len(payload) > MAX_EVENT_PAYLOAD_KEYS:
            raise ValueError("payload has too many keys")
        for key in payload:
            if not isinstance(key, str) or not key or len(key) > MAX_EVENT_PAYLOAD_KEY_LEN:
                raise ValueError("payload keys are invalid")
        try:
            raw = json.dumps(payload, default=str)
        except TypeError as exc:
            raise ValueError("payload is not JSON-serializable") from exc
        if len(raw.encode("utf-8")) > MAX_EVENT_PAYLOAD_BYTES:
            raise ValueError("payload too large")
        return cap_event_payload(payload)


class SessionOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    game_id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None
    total_points: int
    total_time_ms: int
    correct_count: int
    attempt_count: int
    levels_completed: int = 0
    total_levels: int | None = None
    game_title: str | None = None

    model_config = {"from_attributes": True}


class GameProgressOut(BaseModel):
    game_id: uuid.UUID
    completed: bool
    levels_completed: int
    total_levels: int | None
    points: int
    accuracy: float
    progress_pct: int | None = None
    plays: int = 0


class ContinueSessionOut(BaseModel):
    session_id: uuid.UUID
    game_id: uuid.UUID
    game_title: str
    game_description: str = ""
    topic_tags: list[str] = Field(default_factory=list)
    difficulty: int = 1
    levels_completed: int
    total_levels: int | None
    total_points: int
    started_at: datetime


class ClassroomCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class ClassroomJoin(BaseModel):
    code: str = Field(min_length=4, max_length=8)


class ClassroomOut(BaseModel):
    id: uuid.UUID
    name: str
    join_code: str
    teacher_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class AssignmentCreate(BaseModel):
    game_id: uuid.UUID


class ClassroomAssignmentOut(BaseModel):
    id: uuid.UUID
    game_id: uuid.UUID
    game_title: str
    created_at: datetime
    completed: bool = False
    points: int = 0
    accuracy: float = 0.0
    levels_completed: int = 0
    total_levels: int | None = None
    progress_pct: int | None = None
    solved_count: int = 0
    in_progress_count: int = 0
    not_started_count: int = 0
    avg_points: float = 0.0
    avg_levels: float = 0.0
    avg_accuracy: float = 0.0


class StudentProgressOut(BaseModel):
    student_id: uuid.UUID
    student_name: str
    student_email: str
    game_id: uuid.UUID
    game_title: str
    completed: bool
    points: int
    accuracy: float
    levels_completed: int
    total_levels: int | None
    progress_pct: int | None = None


class ClassroomDetailOut(BaseModel):
    id: uuid.UUID
    name: str
    join_code: str
    teacher_id: uuid.UUID
    is_teacher: bool
    member_count: int
    assignments: list[ClassroomAssignmentOut]
    progress: list[StudentProgressOut]
    solved_assignments: int = 0
    total_assignments: int = 0
    students_solved_all: int = 0


class SessionDetail(SessionOut):
    game_title: str | None = None


class DashboardStats(BaseModel):
    total_sessions: int
    total_points: int
    avg_accuracy: float
    avg_task_time_ms: float
    games_solved: int = 0
    levels_solved: int = 0
    recent_sessions: list[SessionDetail]
    per_game: list[dict[str, Any]]
    by_topic: list[dict[str, Any]]


class PlatformStats(BaseModel):
    users: int
    games: int
    sessions: int
    creators: int
    learners: int


class GameAnalyticsOut(BaseModel):
    game_id: uuid.UUID
    title: str
    topic: str
    difficulty: int
    views: int
    unique_visitors: int
    plays: int
    unique_players: int
    view_to_play_rate: float
    total_time_ms: int
    avg_time_ms: float
    avg_levels_completed: float
    completion_rate: float
    avg_accuracy: float
    avg_score: float


class LevelFunnelOut(BaseModel):
    level: int
    sessions_reached: int
    reach_rate: float


class TaskStatOut(BaseModel):
    task_id: str
    completions: int
    avg_duration_ms: float


class DailyViewsOut(BaseModel):
    date: str
    views: int


class RecentSessionOut(BaseModel):
    session_id: uuid.UUID
    user_email: str
    started_at: datetime
    duration_ms: int
    levels_completed: int
    total_levels: int | None
    completed: bool
    points: int
    accuracy: float


class GameAnalyticsDetailOut(GameAnalyticsOut):
    level_funnel: list[LevelFunnelOut]
    task_stats: list[TaskStatOut]
    daily_views: list[DailyViewsOut]
    recent_sessions: list[RecentSessionOut]
    event_counts: dict[str, int]


class GameViewIn(BaseModel):
    visitor_id: str | None = Field(default=None, max_length=64)


class RecommendationOut(BaseModel):
    game: GameOut
    reason: str
    score: float
