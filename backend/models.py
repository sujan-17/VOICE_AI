import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


class UserRole(str, enum.Enum):
    student = "student"
    staff = "staff"


class ChatMode(str, enum.Enum):
    assistant = "assistant"
    evaluator = "evaluator"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, index=True)
    student_code: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True)
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    sessions: Mapped[list["ChatSession"]] = relationship("ChatSession", back_populates="user")
    evaluation_attempts: Mapped[list["EvaluationAttempt"]] = relationship(
        "EvaluationAttempt",
        back_populates="user",
    )


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    steps: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    rubric: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    sessions: Mapped[list["ChatSession"]] = relationship("ChatSession", back_populates="experiment")
    evaluation_attempts: Mapped[list["EvaluationAttempt"]] = relationship(
        "EvaluationAttempt",
        back_populates="experiment",
    )


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"), nullable=False, index=True)
    mode: Mapped[ChatMode] = mapped_column(Enum(ChatMode), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="sessions")
    experiment: Mapped["Experiment"] = relationship("Experiment", back_populates="sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )
    metrics: Mapped[list["PerformanceMetric"]] = relationship(
        "PerformanceMetric",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    evaluation_attempts: Mapped[list["EvaluationAttempt"]] = relationship(
        "EvaluationAttempt",
        back_populates="session",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")


class EvaluationAttempt(Base):
    __tablename__ = "evaluation_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False, index=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="evaluation_attempts")
    experiment: Mapped["Experiment"] = relationship("Experiment", back_populates="evaluation_attempts")
    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="evaluation_attempts")


class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False, index=True)
    request_type: Mapped[str] = mapped_column(String(20), nullable=False)
    total_latency: Mapped[float] = mapped_column(Float, nullable=False)
    llm_latency: Mapped[float] = mapped_column(Float, nullable=False)
    stt_latency: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rtf: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="metrics")
