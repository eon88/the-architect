import logging
import datetime
import random
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from config import CORS_ORIGINS, configure_logging
from database import SessionLocal, User, PillarState, JournalEntry, UserFact, PILLARS
from pipeline import ArchitectPipeline
from auth import create_session, get_current_user_id
from context import build_user_context

_STATIC_DIR = Path(__file__).parent / "static"

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="The Architect", version="0.2.0")
pipeline = ArchitectPipeline()

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# ---------------------------------------------------------------------------
# Seed questions — first 7 sessions are sequential (one per pillar), after
# that we target the most-neglected pillar dynamically.
# ---------------------------------------------------------------------------

_SEED_QUESTIONS: list[tuple[str, str]] = [
    ("Social",             "Who in your life actually pushes you to be better, and who is just taking up space?"),
    ("Financial",          "If your income vanished tomorrow, how many days could you survive?"),
    ("Spiritual",          "When was the last time you felt peace without a screen or distraction?"),
    ("Craft/Career",       "What is one skill you'd spend 10,000 hours mastering just for the pride of it?"),
    ("Emotional/Intimacy", "Do the people closest to you feel truly seen and heard by you?"),
    ("Intellectual",       "What is a belief you held for years that you now know is wrong?"),
    ("Legacy",             "If you disappeared tomorrow, what would the world actually miss?"),
]


def _get_seed_question(entry_count: int, pillar_states: list[dict]) -> str:
    if entry_count < len(_SEED_QUESTIONS):
        return _SEED_QUESTIONS[entry_count][1]

    # After baseline is built, target the most-neglected paused pillar
    paused = [p for p in pillar_states if p["status"] == "Paused"]
    if paused:
        most_neglected = max(paused, key=lambda p: p["days_in_state"])
        for pillar, question in _SEED_QUESTIONS:
            if pillar == most_neglected["name"]:
                return question

    return random.choice(_SEED_QUESTIONS)[1]


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    name: str = "Architect"

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v[:200]


class LoginResponse(BaseModel):
    user_id: int
    email: str
    token: str


class MorningRitualResponse(BaseModel):
    message: str
    seed_question: str


class JournalRequest(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Journal entry must not be blank")
        if len(v) > 10_000:
            raise ValueError("Journal entry is too long (max 10,000 characters)")
        return v


class JournalResponse(BaseModel):
    status: str
    pillar_updated: str
    momentum: str


class WeeklyReviewResponse(BaseModel):
    moved: list[str]
    stalled: list[str]
    pattern: str
    directive: str
    entries_this_week: int


class PillarResponse(BaseModel):
    name: str
    status: str


class HealthResponse(BaseModel):
    status: str


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_user(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def read_index():
    return FileResponse(str(_STATIC_DIR / "index.html"))


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health():
    return {"status": "ok"}


@app.post("/auth/login", response_model=LoginResponse, tags=["auth"])
async def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        user = User(email=data.email, full_name=data.name)
        db.add(user)
        db.flush()
        for pillar in PILLARS:
            db.add(PillarState(user_id=user.id, pillar_name=pillar, status="Paused"))
        db.commit()
        db.refresh(user)
        logger.info("New user registered: %s", data.email)
    else:
        logger.info("Existing user logged in: %s", data.email)

    token = create_session(user.id)
    return LoginResponse(user_id=user.id, email=user.email, token=token)


@app.get("/ritual/morning", response_model=MorningRitualResponse, tags=["ritual"])
async def get_morning_ritual(user: User = Depends(require_user), db: Session = Depends(get_db)):
    ctx = build_user_context(user.id, db)

    seed_question = _get_seed_question(ctx.entry_count, ctx.pillar_states)

    if not ctx.recent_entries:
        return MorningRitualResponse(
            message="Welcome to Day 1. Your journey begins with a single step. Go do one thing today that the man you want to be would do.",
            seed_question=seed_question,
        )

    result = pipeline.process_journal(ctx.recent_entries[0], ctx)
    return MorningRitualResponse(message=result["message"], seed_question=seed_question)


@app.post("/ritual/evening", response_model=JournalResponse, tags=["ritual"])
async def submit_evening_journal(
    data: JournalRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    # Build context BEFORE adding today's entry so the pipeline sees prior history
    ctx = build_user_context(user.id, db)

    result = pipeline.process_journal(data.content, ctx)

    # Persist journal entry
    entry = JournalEntry(
        user_id=user.id,
        content=data.content,
        pillar_associated=result["pillar"],
    )
    db.add(entry)

    # Update pillar state
    pillar = (
        db.query(PillarState)
        .filter(PillarState.user_id == user.id, PillarState.pillar_name == result["pillar"])
        .first()
    )
    if pillar:
        pillar.status = result["momentum"]
        pillar.last_updated = datetime.datetime.utcnow()

    db.commit()

    # Extract and store new facts (runs after commit so entry is saved)
    new_facts = pipeline.extract_facts(data.content, ctx.user_facts)
    if new_facts:
        for fact in new_facts:
            db.add(UserFact(user_id=user.id, content=fact))
        db.commit()
        logger.info("Stored %d new fact(s) for user_id=%d", len(new_facts), user.id)

    logger.info("Evening journal processed for user_id=%d, pillar=%s", user.id, result["pillar"])
    return JournalResponse(
        status="success",
        pillar_updated=result["pillar"],
        momentum=result["momentum"],
    )


@app.get("/ritual/weekly", response_model=WeeklyReviewResponse, tags=["ritual"])
async def get_weekly_review(user: User = Depends(require_user), db: Session = Depends(get_db)):
    since = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    recent = (
        db.query(JournalEntry)
        .filter(JournalEntry.user_id == user.id, JournalEntry.timestamp >= since)
        .order_by(JournalEntry.timestamp.asc())
        .all()
    )

    ctx = build_user_context(user.id, db)

    if not recent:
        return WeeklyReviewResponse(
            moved=["No entries this week yet."],
            stalled=["All pillars — nothing to review without journal entries."],
            pattern="Come back after you've written a few entries this week.",
            directive="Write your first entry tonight.",
            entries_this_week=0,
        )

    entries = [
        {"date": e.timestamp.strftime("%A %d %b"), "content": e.content}
        for e in recent
    ]

    result = pipeline.generate_weekly_review(entries, ctx)
    return WeeklyReviewResponse(**result, entries_this_week=len(recent))


@app.get("/user/pillars", response_model=list[PillarResponse], tags=["user"])
async def get_pillars(user: User = Depends(require_user), db: Session = Depends(get_db)):
    pillars = db.query(PillarState).filter(PillarState.user_id == user.id).all()
    return [PillarResponse(name=p.pillar_name, status=p.status) for p in pillars]
