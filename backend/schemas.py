from datetime import datetime

from pydantic import BaseModel, Field

from models import UserRole


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=4)


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=6, max_length=128)
    role: UserRole
    role_id: str = Field(min_length=2, max_length=50)
    department: str | None = Field(default=None, max_length=120)


class GoogleLoginRequest(BaseModel):
    token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    full_name: str
    email: str
    role_id: str | None = None


class UserSummary(BaseModel):
    id: int
    full_name: str
    email: str
    role: UserRole
    role_id: str | None = None
    department: str | None = None


class ExperimentCreate(BaseModel):
    slug: str
    title: str
    objective: str
    steps: list[str]


class ExperimentUpdate(BaseModel):
    title: str
    objective: str
    steps: list[str]


class ExperimentOut(BaseModel):
    slug: str
    title: str
    objective: str
    steps: list[str]
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TextRequest(BaseModel):
    text: str
    mode: str
    experiment_id: str
    session_id: str | None = None


class AudioRequest(BaseModel):
    text: str
    session_id: str


class ChatResponse(BaseModel):
    session_id: str
    user_said: str
    ai_response: str


class StaffDashboardSummary(BaseModel):
    total_students: int
    total_experiments: int
    total_sessions: int
    average_score: float


class StudentDashboardSummary(BaseModel):
    total_sessions: int
    completed_evaluations: int
    average_score: float
    recent_experiments: list[str]
