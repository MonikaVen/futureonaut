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


class ContinueSessionOut(BaseModel):
    session_id: uuid.UUID
    game_id: uuid.UUID
    game_title: str
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


class StudentProgressOut(BaseModel):
    student_name: str
    student_email: str
    game_id: uuid.UUID
    game_title: str
    completed: bool
    points: int
    accuracy: float
    levels_completed: int
    total_levels: int | None


class ClassroomDetailOut(BaseModel):
    id: uuid.UUID
    name: str
    join_code: str
    teacher_id: uuid.UUID
    is_teacher: bool
    member_count: int
    assignments: list[dict[str, Any]]
    progress: list[StudentProgressOut]


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
