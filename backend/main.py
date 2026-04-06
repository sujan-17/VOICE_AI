import os
import re
import time
import uuid

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from auth import authenticate_user, create_access_token, get_current_user, get_password_hash, require_role
from config import settings
from db import Base, SessionLocal, engine, get_db
from gemini_service import GeminiService
from metrics import PerformanceMetrics
from models import ChatMessage, ChatMode, ChatSession, EvaluationAttempt, Experiment, PerformanceMetric, User, UserRole
from schemas import (
    AudioRequest,
    ChatResponse,
    ExperimentCreate,
    ExperimentOut,
    ExperimentUpdate,
    GoogleLoginRequest,
    LoginRequest,
    RegisterRequest,
    StudentDashboardSummary,
    TextRequest,
    TokenResponse,
    UserSummary,
)
from seed_data import initialize_seed_data
from stt_service import STTService
from tts_service import TTSService

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

stt = STTService()
llm = GeminiService()
tts = TTSService()
perf = PerformanceMetrics()

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        initialize_seed_data(db)
    finally:
        db.close()


def serialize_messages(messages):
    return [
        {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "created_at": message.created_at.isoformat(),
        }
        for message in messages
    ]


def serialize_experiment(experiment: Experiment):
    return {
        "id": experiment.id,
        "slug": experiment.slug,
        "title": experiment.title,
        "objective": experiment.objective,
        "steps": experiment.steps or [],
        "created_at": experiment.created_at.isoformat(),
        "updated_at": experiment.updated_at.isoformat(),
    }


def get_experiment_by_slug(db: Session, experiment_slug: str) -> Experiment:
    experiment = db.query(Experiment).filter(Experiment.slug == experiment_slug).first()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment


def get_or_create_session(
    db: Session,
    current_user: User,
    experiment: Experiment,
    mode: str,
    session_id: str | None,
) -> ChatSession:
    if mode not in {ChatMode.assistant.value, ChatMode.evaluator.value}:
        raise HTTPException(status_code=400, detail="Invalid chat mode")

    session = None
    if session_id:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
            .first()
        )
        if session and session.experiment_id != experiment.id:
            raise HTTPException(status_code=400, detail="Session experiment mismatch")

    if session:
        return session

    session = ChatSession(
        id=session_id or str(uuid.uuid4()),
        user_id=current_user.id,
        experiment_id=experiment.id,
        mode=ChatMode(mode),
        title=f"{experiment.title} - {mode.title()}",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def build_history(session: ChatSession):
    messages = session.messages[-settings.max_history_messages :]
    return [{"role": message.role, "content": message.content} for message in messages]


def extract_score(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*/\s*10", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def record_message_pair(db: Session, session: ChatSession, user_text: str, ai_text: str):
    db.add(ChatMessage(session_id=session.id, role="user", content=user_text))
    db.add(ChatMessage(session_id=session.id, role="assistant", content=ai_text))
    session.updated_at = func.now()
    db.commit()


def record_assistant_message(db: Session, session: ChatSession, ai_text: str):
    db.add(ChatMessage(session_id=session.id, role="assistant", content=ai_text))
    session.updated_at = func.now()
    db.commit()


def is_evaluator_control_message(text: str) -> bool:
    normalized = " ".join((text or "").strip().lower().split())
    return normalized in {
        "start",
        "start viva",
        "start evaluation",
        "begin",
        "begin viva",
        "begin evaluation",
        "next",
        "next question",
        "ask next question",
        "continue",
        "continue viva",
        "continue evaluation",
        "go on",
        "proceed",
        "what",
        "what?",
        "ok",
        "okay",
        "yes",
    }


def record_metric(db: Session, session_id: str, metric_payload: dict):
    metric = PerformanceMetric(session_id=session_id, **metric_payload)
    db.add(metric)
    db.commit()


def maybe_record_evaluation(db: Session, current_user: User, session: ChatSession, ai_text: str):
    if session.mode != ChatMode.evaluator or current_user.role != UserRole.student:
        return

    score = extract_score(ai_text)
    if score is None:
        return

    existing = (
        db.query(EvaluationAttempt)
        .filter(EvaluationAttempt.session_id == session.id)
        .first()
    )
    if existing:
        existing.score = score
        existing.feedback = ai_text
    else:
        db.add(
            EvaluationAttempt(
                user_id=current_user.id,
                experiment_id=session.experiment_id,
                session_id=session.id,
                score=score,
                feedback=ai_text,
            )
        )
    db.commit()


def safe_round(value, digits=2):
    return round(float(value), digits) if value is not None else 0.0


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user.email)
    return TokenResponse(
        access_token=token,
        role=user.role,
        full_name=user.full_name,
        email=user.email,
        role_id=user.student_code,
    )


@app.post("/auth/google", response_model=TokenResponse)
def google_login(payload: GoogleLoginRequest, db: Session = Depends(get_db)):
    if not settings.google_client_id:
        raise HTTPException(status_code=500, detail="Google login is not configured")

    try:
        idinfo = id_token.verify_oauth2_token(
            payload.token,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid Google token") from exc

    email = (idinfo.get("email") or "").strip().lower()
    full_name = (idinfo.get("name") or "Google User").strip()
    email_verified = bool(idinfo.get("email_verified"))

    if not email or not email_verified:
        raise HTTPException(status_code=400, detail="Google account email is not available or not verified")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            full_name=full_name,
            email=email,
            password_hash=get_password_hash(str(uuid.uuid4())),
            role=UserRole.student,
            student_code=None,
            department=None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token(user.email)
    return TokenResponse(
        access_token=token,
        role=user.role,
        full_name=user.full_name,
        email=user.email,
        role_id=user.student_code,
    )


@app.get("/auth/me", response_model=UserSummary)
def get_me(current_user: User = Depends(get_current_user)):
    return UserSummary(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        role=current_user.role,
        role_id=current_user.student_code,
        department=current_user.department,
    )


@app.post("/auth/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing_email = db.query(User).filter(User.email == payload.email.strip()).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    existing_role_id = db.query(User).filter(User.student_code == payload.role_id.strip()).first()
    if existing_role_id:
        raise HTTPException(status_code=400, detail="This student or staff ID is already in use")

    user = User(
        full_name=payload.full_name.strip(),
        email=payload.email.strip(),
        password_hash=get_password_hash(payload.password),
        role=payload.role,
        student_code=payload.role_id.strip(),
        department=(payload.department or "").strip() or None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.email)
    return TokenResponse(
        access_token=token,
        role=user.role,
        full_name=user.full_name,
        email=user.email,
        role_id=user.student_code,
    )


@app.get("/experiments", response_model=list[ExperimentOut])
def list_experiments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    del current_user
    return db.query(Experiment).order_by(Experiment.title.asc()).all()


@app.get("/experiments/{slug}", response_model=ExperimentOut)
def get_experiment(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    del current_user
    return get_experiment_by_slug(db, slug)


@app.get("/student/dashboard")
def student_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.student)),
):
    total_sessions = db.query(ChatSession).filter(ChatSession.user_id == current_user.id).count()
    assistant_sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id, ChatSession.mode == ChatMode.assistant)
        .count()
    )
    evaluator_sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id, ChatSession.mode == ChatMode.evaluator)
        .count()
    )
    completed_evaluations = (
        db.query(EvaluationAttempt).filter(EvaluationAttempt.user_id == current_user.id).count()
    )
    average_score = (
        db.query(func.avg(EvaluationAttempt.score))
        .filter(EvaluationAttempt.user_id == current_user.id, EvaluationAttempt.score.is_not(None))
        .scalar()
    ) or 0.0
    best_score = (
        db.query(func.max(EvaluationAttempt.score))
        .filter(EvaluationAttempt.user_id == current_user.id, EvaluationAttempt.score.is_not(None))
        .scalar()
    ) or 0.0
    average_latency = (
        db.query(func.avg(PerformanceMetric.total_latency))
        .join(ChatSession, ChatSession.id == PerformanceMetric.session_id)
        .filter(ChatSession.user_id == current_user.id)
        .scalar()
    ) or 0.0

    recent_sessions = (
        db.query(ChatSession)
        .options(joinedload(ChatSession.experiment), joinedload(ChatSession.messages))
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .limit(5)
        .all()
    )

    summary = StudentDashboardSummary(
        total_sessions=total_sessions,
        completed_evaluations=completed_evaluations,
        average_score=round(float(average_score), 2),
        recent_experiments=[session.experiment.title for session in recent_sessions],
    )

    recent_history = [
        {
            "session_id": session.id,
            "mode": session.mode.value,
            "experiment": session.experiment.title,
            "updated_at": session.updated_at.isoformat(),
            "message_count": len(session.messages),
        }
        for session in recent_sessions
    ]

    scores = [
        {
            "experiment": attempt.experiment.title,
            "score": attempt.score,
            "created_at": attempt.created_at.isoformat(),
        }
        for attempt in (
            db.query(EvaluationAttempt)
            .options(joinedload(EvaluationAttempt.experiment))
            .filter(EvaluationAttempt.user_id == current_user.id)
            .order_by(EvaluationAttempt.created_at.desc())
            .limit(8)
            .all()
        )
    ]

    experiment_progress = []
    experiments = db.query(Experiment).order_by(Experiment.title.asc()).all()
    for experiment in experiments:
        attempt_scores = [
            item.score
            for item in (
                db.query(EvaluationAttempt)
                .filter(
                    EvaluationAttempt.user_id == current_user.id,
                    EvaluationAttempt.experiment_id == experiment.id,
                    EvaluationAttempt.score.is_not(None),
                )
                .order_by(EvaluationAttempt.created_at.desc())
                .all()
            )
        ]
        session_count = (
            db.query(ChatSession)
            .filter(ChatSession.user_id == current_user.id, ChatSession.experiment_id == experiment.id)
            .count()
        )
        experiment_progress.append(
            {
                "slug": experiment.slug,
                "title": experiment.title,
                "session_count": session_count,
                "attempt_count": len(attempt_scores),
                "latest_score": attempt_scores[0] if attempt_scores else None,
                "best_score": max(attempt_scores) if attempt_scores else None,
            }
        )

    voice_metrics = (
        db.query(func.avg(PerformanceMetric.total_latency), func.avg(PerformanceMetric.rtf))
        .join(ChatSession, ChatSession.id == PerformanceMetric.session_id)
        .filter(ChatSession.user_id == current_user.id, PerformanceMetric.request_type == "Voice")
        .first()
    )
    text_latency = (
        db.query(func.avg(PerformanceMetric.total_latency))
        .join(ChatSession, ChatSession.id == PerformanceMetric.session_id)
        .filter(ChatSession.user_id == current_user.id, PerformanceMetric.request_type == "Text")
        .scalar()
    ) or 0.0

    return {
        "summary": {
            **summary.model_dump(),
            "assistant_sessions": assistant_sessions,
            "evaluator_sessions": evaluator_sessions,
            "best_score": safe_round(best_score),
            "average_latency": safe_round(average_latency),
        },
        "recent_history": recent_history,
        "scores": scores,
        "experiment_progress": experiment_progress,
        "performance": {
            "average_voice_latency": safe_round(voice_metrics[0] if voice_metrics else 0.0),
            "average_text_latency": safe_round(text_latency),
            "average_rtf": safe_round(voice_metrics[1] if voice_metrics else 0.0),
        },
    }


@app.get("/student/history")
def student_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.student)),
):
    sessions = (
        db.query(ChatSession)
        .options(joinedload(ChatSession.experiment), joinedload(ChatSession.messages))
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    return [
        {
            "session_id": session.id,
            "mode": session.mode.value,
            "experiment": session.experiment.title,
            "updated_at": session.updated_at.isoformat(),
            "messages": serialize_messages(session.messages),
        }
        for session in sessions
    ]


@app.get("/staff/dashboard")
def staff_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.staff)),
):
    del current_user
    average_score = db.query(func.avg(EvaluationAttempt.score)).scalar() or 0.0
    summary = {
        "total_students": db.query(User).filter(User.role == UserRole.student).count(),
        "total_experiments": db.query(Experiment).count(),
        "total_sessions": db.query(ChatSession).count(),
        "average_score": round(float(average_score), 2),
    }

    students = (
        db.query(User)
        .filter(User.role == UserRole.student)
        .order_by(User.full_name.asc())
        .all()
    )
    student_cards = []
    for student in students:
        student_average = (
            db.query(func.avg(EvaluationAttempt.score))
            .filter(EvaluationAttempt.user_id == student.id, EvaluationAttempt.score.is_not(None))
            .scalar()
        ) or 0.0
        student_cards.append(
            {
                "id": student.id,
                "full_name": student.full_name,
                "email": student.email,
                "student_code": student.student_code,
                "department": student.department,
                "average_score": round(float(student_average), 2),
                "session_count": db.query(ChatSession).filter(ChatSession.user_id == student.id).count(),
                "evaluation_count": db.query(EvaluationAttempt).filter(EvaluationAttempt.user_id == student.id).count(),
            }
        )

    experiment_cards = []
    experiments = db.query(Experiment).order_by(Experiment.updated_at.desc()).all()
    for experiment in experiments:
        session_count = db.query(ChatSession).filter(ChatSession.experiment_id == experiment.id).count()
        evaluation_count = db.query(EvaluationAttempt).filter(EvaluationAttempt.experiment_id == experiment.id).count()
        average_experiment_score = (
            db.query(func.avg(EvaluationAttempt.score))
            .filter(EvaluationAttempt.experiment_id == experiment.id, EvaluationAttempt.score.is_not(None))
            .scalar()
        ) or 0.0
        experiment_cards.append(
            {
                **serialize_experiment(experiment),
                "session_count": session_count,
                "evaluation_count": evaluation_count,
                "average_score": safe_round(average_experiment_score),
            }
        )

    recent_evaluations = [
        {
            "student_name": attempt.user.full_name,
            "experiment_title": attempt.experiment.title,
            "score": attempt.score,
            "created_at": attempt.created_at.isoformat(),
        }
        for attempt in (
            db.query(EvaluationAttempt)
            .options(joinedload(EvaluationAttempt.user), joinedload(EvaluationAttempt.experiment))
            .order_by(EvaluationAttempt.created_at.desc())
            .limit(8)
            .all()
        )
    ]

    return {
        "summary": summary,
        "students": student_cards,
        "experiments": experiment_cards,
        "recent_evaluations": recent_evaluations,
    }


@app.get("/staff/students/{student_id}")
def get_student_detail(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.staff)),
):
    del current_user
    student = db.query(User).filter(User.id == student_id, User.role == UserRole.student).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    sessions = (
        db.query(ChatSession)
        .options(joinedload(ChatSession.experiment), joinedload(ChatSession.messages))
        .filter(ChatSession.user_id == student.id)
        .order_by(ChatSession.updated_at.desc())
        .limit(10)
        .all()
    )
    attempts = (
        db.query(EvaluationAttempt)
        .options(joinedload(EvaluationAttempt.experiment))
        .filter(EvaluationAttempt.user_id == student.id)
        .order_by(EvaluationAttempt.created_at.desc())
        .all()
    )
    average_latency = (
        db.query(func.avg(PerformanceMetric.total_latency))
        .join(ChatSession, ChatSession.id == PerformanceMetric.session_id)
        .filter(ChatSession.user_id == student.id)
        .scalar()
    ) or 0.0

    return {
        "student": {
            "id": student.id,
            "full_name": student.full_name,
            "email": student.email,
            "student_code": student.student_code,
            "department": student.department,
        },
        "summary": {
            "session_count": db.query(ChatSession).filter(ChatSession.user_id == student.id).count(),
            "evaluation_count": len(attempts),
            "average_score": safe_round(sum((attempt.score or 0) for attempt in attempts) / len(attempts)) if attempts else 0.0,
            "best_score": safe_round(max((attempt.score or 0) for attempt in attempts)) if attempts else 0.0,
            "average_latency": safe_round(average_latency),
        },
        "recent_sessions": [
            {
                "session_id": session.id,
                "experiment": session.experiment.title,
                "mode": session.mode.value,
                "updated_at": session.updated_at.isoformat(),
                "message_count": len(session.messages),
            }
            for session in sessions
        ],
        "evaluations": [
            {
                "experiment": attempt.experiment.title,
                "score": attempt.score,
                "feedback": attempt.feedback,
                "created_at": attempt.created_at.isoformat(),
            }
            for attempt in attempts[:8]
        ],
    }


@app.post("/staff/experiments", response_model=ExperimentOut)
def create_experiment(
    payload: ExperimentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.staff)),
):
    existing = db.query(Experiment).filter(Experiment.slug == payload.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="An experiment with this slug already exists")

    experiment = Experiment(
        slug=payload.slug,
        title=payload.title,
        objective=payload.objective,
        steps=payload.steps,
        rubric={},
        created_by_id=current_user.id,
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


@app.put("/staff/experiments/{slug}")
def update_experiment(
    slug: str,
    payload: ExperimentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.staff)),
):
    del current_user
    experiment = get_experiment_by_slug(db, slug)
    experiment.title = payload.title
    experiment.objective = payload.objective
    experiment.steps = payload.steps
    db.commit()
    db.refresh(experiment)
    return serialize_experiment(experiment)


@app.delete("/staff/experiments/{slug}")
def delete_experiment(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.staff)),
):
    del current_user
    experiment = get_experiment_by_slug(db, slug)
    linked_sessions = db.query(ChatSession).filter(ChatSession.experiment_id == experiment.id).count()
    if linked_sessions > 0:
        raise HTTPException(
            status_code=400,
            detail="This experiment already has student sessions, so it cannot be deleted.",
        )

    db.delete(experiment)
    db.commit()
    return {"message": f"Experiment '{slug}' deleted successfully."}


@app.get("/staff/students", response_model=list[UserSummary])
def list_students(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.staff)),
):
    del current_user
    students = db.query(User).filter(User.role == UserRole.student).order_by(User.full_name.asc()).all()
    return [
        UserSummary(
            id=student.id,
            full_name=student.full_name,
            email=student.email,
            role=student.role,
            role_id=student.student_code,
            department=student.department,
        )
        for student in students
    ]


@app.post("/process-text", response_model=ChatResponse)
async def process_text(
    request: TextRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    perf.start_timer()

    experiment = get_experiment_by_slug(db, request.experiment_id)
    session = get_or_create_session(db, current_user, experiment, request.mode, request.session_id)
    history = build_history(session)

    llm_start = time.perf_counter()
    ai_text = await llm.get_response(
        user_text=request.text,
        mode=request.mode,
        experiment=experiment,
        history=history,
    )
    llm_latency = time.perf_counter() - llm_start
    total_latency = perf.stop_timer()

    if request.mode == ChatMode.evaluator.value and is_evaluator_control_message(request.text):
        record_assistant_message(db, session, ai_text)
    else:
        record_message_pair(db, session, request.text, ai_text)
    metric_payload = perf.as_record("Text", total_latency, llm_latency)
    record_metric(db, session.id, metric_payload)
    maybe_record_evaluation(db, current_user, session, ai_text)

    return ChatResponse(session_id=session.id, user_said=request.text, ai_response=ai_text)


@app.post("/process-voice", response_model=ChatResponse)
async def process_voice(
    audio: UploadFile = File(...),
    mode: str = Form(...),
    experiment_id: str = Form(...),
    session_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    perf.start_timer()
    experiment = get_experiment_by_slug(db, experiment_id)
    session = get_or_create_session(db, current_user, experiment, mode, session_id)

    audio_bytes = await audio.read()
    file_ext = audio.filename.split(".")[-1] if audio.filename and "." in audio.filename else "webm"
    tmp_path = os.path.join(OUTPUT_DIR, f"temp_{session.id}.{file_ext}")

    with open(tmp_path, "wb") as temp_file:
        temp_file.write(audio_bytes)

    stt_start = time.perf_counter()
    try:
        transcript, audio_duration = stt.transcribe(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    stt_latency = time.perf_counter() - stt_start
    rtf = perf.calculate_rtf(stt_latency, audio_duration)

    if not transcript.strip():
        fallback = "I didn't catch that. Please try speaking again or type your message."
        return ChatResponse(session_id=session.id, user_said="[Silence Detected]", ai_response=fallback)

    history = build_history(session)
    llm_start = time.perf_counter()
    ai_text = await llm.get_response(
        user_text=transcript,
        mode=mode,
        experiment=experiment,
        history=history,
    )
    llm_latency = time.perf_counter() - llm_start
    total_latency = perf.stop_timer()

    if mode == ChatMode.evaluator.value and is_evaluator_control_message(transcript):
        record_assistant_message(db, session, ai_text)
    else:
        record_message_pair(db, session, transcript, ai_text)
    metric_payload = perf.as_record("Voice", total_latency, llm_latency, stt_latency, rtf)
    record_metric(db, session.id, metric_payload)
    maybe_record_evaluation(db, current_user, session, ai_text)

    return ChatResponse(session_id=session.id, user_said=transcript, ai_response=ai_text)


@app.post("/generate-audio")
async def generate_audio(
    request: AudioRequest,
    current_user: User = Depends(get_current_user),
):
    del current_user
    output_filename = f"{request.session_id}_response.mp3"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    await tts.text_to_speech(request.text, output_path)
    cache_buster = str(uuid.uuid4())[:8]
    return {"audio_url": f"{settings.public_base_url}/outputs/{output_filename}?v={cache_buster}"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
